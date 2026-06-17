"""US BigQuery full text retrieval for Top5 candidates."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from tech_cartography.domain.fulltext_record import FullTextRecord
from tech_cartography.evidence.evidence_coverage import (
  detect_independent_claims,
  evaluate_evidence_coverage,
  extract_examples,
  extract_measured_properties,
)
from tech_cartography.reports.project_export import (
  build_output_directory,
  save_records_csv,
  save_retrieval_summary,
)
from tech_cartography.retrieval.bigquery_env import (
  bytes_to_gb,
  estimate_usd_from_bytes,
  gb_to_bytes,
  resolve_project_id,
  usd_to_bytes,
)
from tech_cartography.retrieval.bigquery_fulltext_query_builder import (
  VALID_FULLTEXT_SCOPES,
  build_us_fulltext_query,
  is_us_publication,
  validate_fulltext_scope,
  validate_us_fulltext_request,
)
from tech_cartography.retrieval.controlled_fulltext_plan import (
  _normalize_publication_number,
  build_controlled_fulltext_plan,
  build_fulltext_execute_preview,
  mark_execute_selected_targets,
  render_manual_fulltext_checklist,
  select_fulltext_execute_targets,
)
from tech_cartography.costs.adaptive_retrieval_controller import (
  build_adaptive_retrieval_plan,
  should_execute_candidate,
  update_remaining_budget,
)
from tech_cartography.costs.cost_ledger import (
  append_cost_ledger_entry,
  build_cost_ledger_entry_from_bigquery_job,
  build_cost_ledger_entry_from_estimate,
  build_public_cost_status,
  cost_ledger_entry_to_dict,
  summarize_cost_ledger,
)
from tech_cartography.costs.internal_cost_policy import CostVisibilityPolicy, InternalCostPolicy
from tech_cartography.retrieval.bigquery_fulltext_availability_probe import (
  QUERY_STRATEGY,
  FulltextAvailabilityProbeResult,
  execute_availability_probe,
  probe_result_to_public_dict,
  save_availability_probe_result,
)
from tech_cartography.retrieval.fulltext_not_found_cache import (
  get_not_found_entry,
  is_known_not_found,
  mark_not_found,
)
from tech_cartography.retrieval.publication_number_variants import build_publication_number_variants
from tech_cartography.retrieval.fulltext_cache import (
  load_fulltext_from_cache,
  save_fulltext_to_cache,
)

ClientFactory = Callable[[str], Any]


@dataclass
class FullTextRetrievalConfig:
  project_id: str | None = None
  dry_run: bool = True
  execute: bool = False
  maximum_bytes_billed_gb: float = 50.0
  output_dir: str = "outputs/top5_fulltext_collection"
  cache_dir: str = "data/runtime/fulltext_cache"
  use_cache: bool = True
  allow_manual_fallback: bool = True
  execute_limit: int = 1
  publication_number: str | None = None
  execute_top_n: int | None = None
  confirm_fulltext_execute: bool = False
  require_fulltext_execute_confirmation: bool = True
  preview_only: bool = False
  fulltext_scope: str = "claims_only"
  maximum_fulltext_usd: float = 10.0
  allow_expensive_fulltext: bool = False
  internal_cost_policy: InternalCostPolicy | None = None
  enable_cost_ledger: bool = True
  global_ledger_path: str = "outputs/cost_ledger/cost_ledger.jsonl"
  run_id: str = ""
  stage_id: str = "top5_fulltext_collection"
  enable_availability_probe: bool = False
  use_not_found_cache: bool = False
  not_found_cache_path: str = "outputs/fulltext_cache/not_found_cache.json"
  max_probe_estimated_usd: float = 0.5
  availability_probe_output_dir: str | None = None

  def maximum_bytes_billed(self) -> int:
    return gb_to_bytes(self.maximum_bytes_billed_gb)

  def resolved_scope(self) -> str:
    return validate_fulltext_scope(self.fulltext_scope)


def _default_client_factory(project_id: str) -> Any:
  from google.cloud import bigquery

  return bigquery.Client(project=project_id)


def _append_ledger_row(
  config: FullTextRetrievalConfig,
  entry: Any,
  ledger_entries: list[dict[str, Any]] | None,
) -> None:
  if not config.enable_cost_ledger:
    return
  row = cost_ledger_entry_to_dict(entry) if not isinstance(entry, dict) else entry
  if ledger_entries is not None:
    ledger_entries.append(row)
  append_cost_ledger_entry(row, config.global_ledger_path)


def evaluate_cost_guard(
  estimated_bytes: int,
  estimated_usd: float,
  config: FullTextRetrievalConfig,
) -> dict[str, Any]:
  max_gb = float(config.maximum_bytes_billed_gb)
  max_usd = float(config.maximum_fulltext_usd)
  policy = config.internal_cost_policy
  effective_max_usd = float(policy.raw_cost_cap_usd) if policy else max_usd
  est_gb = bytes_to_gb(int(estimated_bytes or 0))
  est_usd = float(estimated_usd or 0.0)

  if estimated_bytes <= 0 and est_usd <= 0:
    return {
      "cost_guard_status": "not_estimated",
      "cost_guard_reason": "Dry-run estimate unavailable",
      "can_execute": False,
      "requires_expensive_confirmation": False,
      "estimated_gb": est_gb,
      "estimated_usd": est_usd,
      "maximum_fulltext_gb": max_gb,
      "maximum_fulltext_usd": max_usd,
      "allow_expensive_fulltext": bool(config.allow_expensive_fulltext),
    }

  if est_usd > effective_max_usd:
    return {
      "cost_guard_status": "blocked_by_usd",
      "cost_guard_reason": f"estimated_usd={est_usd:.4f} exceeds internal cap={effective_max_usd}",
      "can_execute": False,
      "requires_expensive_confirmation": False,
      "estimated_gb": est_gb,
      "estimated_usd": est_usd,
      "maximum_fulltext_gb": max_gb,
      "maximum_fulltext_usd": effective_max_usd,
      "allow_expensive_fulltext": bool(config.allow_expensive_fulltext),
    }

  if est_gb <= max_gb:
    return {
      "cost_guard_status": "pass",
      "cost_guard_reason": "Within GB and USD limits",
      "can_execute": True,
      "requires_expensive_confirmation": False,
      "estimated_gb": est_gb,
      "estimated_usd": est_usd,
      "maximum_fulltext_gb": max_gb,
      "maximum_fulltext_usd": effective_max_usd,
      "allow_expensive_fulltext": bool(config.allow_expensive_fulltext),
    }

  if policy and est_usd <= effective_max_usd:
    return {
      "cost_guard_status": "allowed_expensive_fulltext",
      "cost_guard_reason": (
        f"estimated_gb={est_gb:.4f} exceeds {max_gb} GB but within internal acquisition policy USD cap"
      ),
      "can_execute": True,
      "requires_expensive_confirmation": False,
      "estimated_gb": est_gb,
      "estimated_usd": est_usd,
      "maximum_fulltext_gb": max_gb,
      "maximum_fulltext_usd": effective_max_usd,
      "allow_expensive_fulltext": True,
    }

  if config.allow_expensive_fulltext:
    return {
      "cost_guard_status": "allowed_expensive_fulltext",
      "cost_guard_reason": (
        f"estimated_gb={est_gb:.4f} exceeds {max_gb} GB but USD {est_usd:.4f} <= {max_usd}; "
        "explicit expensive approval granted"
      ),
      "can_execute": True,
      "requires_expensive_confirmation": False,
      "estimated_gb": est_gb,
      "estimated_usd": est_usd,
      "maximum_fulltext_gb": max_gb,
      "maximum_fulltext_usd": max_usd,
      "allow_expensive_fulltext": True,
    }

  return {
    "cost_guard_status": "blocked_by_gb_but_usd_allowed_requires_confirmation",
    "cost_guard_reason": (
      f"estimated_gb={est_gb:.4f} exceeds {max_gb} GB but estimated_usd={est_usd:.4f} <= {max_usd}; "
      "add --allow-expensive-fulltext to execute"
    ),
    "can_execute": False,
    "requires_expensive_confirmation": True,
    "estimated_gb": est_gb,
    "estimated_usd": est_usd,
    "maximum_fulltext_gb": max_gb,
    "maximum_fulltext_usd": max_usd,
    "allow_expensive_fulltext": False,
  }


def _execution_bytes_cap(config: FullTextRetrievalConfig, estimated_bytes: int) -> int:
  gb_cap = config.maximum_bytes_billed()
  usd_cap = usd_to_bytes(config.maximum_fulltext_usd)
  if config.allow_expensive_fulltext or config.internal_cost_policy:
    return max(gb_cap, int(estimated_bytes or 0), usd_cap)
  return gb_cap


def _enrich_record_metadata(
  record: dict[str, Any],
  *,
  execute_selected: bool | None = None,
  execute_selection_reason: str | None = None,
  dry_run: dict[str, Any] | None = None,
  cost_guard: dict[str, Any] | None = None,
  config: FullTextRetrievalConfig | None = None,
) -> dict[str, Any]:
  enriched = dict(record)
  if execute_selected is not None:
    enriched["execute_selected"] = execute_selected
  if execute_selection_reason:
    enriched["execute_selection_reason"] = execute_selection_reason
  if config:
    enriched["fulltext_scope"] = config.resolved_scope()
    enriched["maximum_fulltext_usd"] = config.maximum_fulltext_usd
    enriched["allow_expensive_fulltext"] = config.allow_expensive_fulltext
  if dry_run:
    enriched["estimated_bytes"] = dry_run.get("estimated_bytes", 0)
    enriched["estimated_gb"] = dry_run.get("estimated_gb", 0.0)
    enriched["estimated_usd"] = dry_run.get("estimated_usd", 0.0)
    enriched["fulltext_scope"] = dry_run.get("fulltext_scope", enriched.get("fulltext_scope"))
  guard = cost_guard or (dry_run or {})
  if guard.get("cost_guard_status"):
    enriched["cost_guard_status"] = guard.get("cost_guard_status")
    enriched["cost_guard_reason"] = guard.get("cost_guard_reason")
  elif dry_run:
    enriched["cost_guard_status"] = dry_run.get("cost_guard_status", "unknown")
    enriched["cost_guard_reason"] = dry_run.get("cost_guard_reason")
  coverage = enriched.get("evidence_coverage") or {}
  enriched["claims_length"] = int(coverage.get("claims_length", 0) or len(str(enriched.get("claims") or "")))
  enriched["description_length"] = int(
    coverage.get("description_length", 0) or len(str(enriched.get("description") or "")),
  )
  return enriched


def _next_action_for_record(record: dict[str, Any]) -> str:
  status = str(record.get("retrieval_status") or "")
  if status in {"retrieved", "cache_hit"}:
    return "run_claim_element_extraction"
  if status == "dry_run_only":
    return "execute_fulltext_with_confirm"
  if status == "skipped_not_selected":
    return "increase_execute_limit_or_select_publication"
  if status == "execute_blocked_confirmation_required":
    return "add_confirm_fulltext_execute"
  if status == "cost_guard_failed":
    return "review_cost_guard_or_manual_fulltext"
  if status == "cost_guard_requires_expensive_confirmation":
    return "add_allow_expensive_fulltext"
  if status == "blocked_by_usd_guard":
    return "reduce_scope_or_increase_usd_limit"
  if status == "allowed_expensive_execute":
    return "run_claim_element_extraction"
  if status in {"manual_required", "unsupported_country"}:
    return "manual_fulltext_review"
  return "review_metadata"


def build_fulltext_execute_results_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
  rows: list[dict[str, Any]] = []
  for record in records:
    rows.append(
      {
        "publication_number": record.get("publication_number"),
        "title": record.get("title"),
        "execute_selected": record.get("execute_selected"),
        "retrieval_status": record.get("retrieval_status"),
        "evidence_level": record.get("evidence_level"),
        "claims_length": record.get("claims_length", 0),
        "description_length": record.get("description_length", 0),
        "estimated_gb": record.get("estimated_gb"),
        "cost_guard_status": record.get("cost_guard_status"),
        "next_action": _next_action_for_record(record),
      },
    )
  return rows


def _safe_str(value: Any) -> str:
  if value is None:
    return ""
  return str(value).strip()


def _candidate_metadata(candidate: dict[str, Any]) -> dict[str, Any]:
  meta: dict[str, Any] = {}
  for key in (
    "application_publication_number",
    "application_number",
    "related_publication_number",
    "grant_publication_number",
    "priority_publication_number",
    "family_publication_number",
  ):
    if candidate.get(key):
      meta[key] = candidate[key]
  nested = candidate.get("metadata")
  if isinstance(nested, dict):
    meta.update({k: v for k, v in nested.items() if v})
  return meta


def _save_probe_artifact(probe: Any, config: FullTextRetrievalConfig) -> None:
  if not config.availability_probe_output_dir:
    return
  try:
    save_availability_probe_result(probe, config.availability_probe_output_dir)
  except Exception:  # noqa: BLE001
    return


def _probe_blocks_fulltext(probe_status: str, scope: str) -> bool:
  if probe_status in {"query_error", "skipped_due_to_probe_cost"}:
    return probe_status == "query_error"
  if probe_status == "found_claims" and scope in {"claims_only", "claims_and_description"}:
    return False
  if probe_status == "found_description_only" and scope == "description_only":
    return False
  if probe_status in {
    "not_found_in_bigquery",
    "found_metadata_only",
    "manual_route_recommended",
    "publication_number_format_mismatch",
  }:
    return True
  if probe_status == "found_description_only" and scope in {"claims_only", "claims_and_description"}:
    return True
  return False


def _retrieval_status_from_probe(probe_status: str, known_cache: bool = False) -> str:
  if known_cache:
    return "skipped_known_not_found"
  mapping = {
    "not_found_in_bigquery": "manual_google_patents_recommended",
    "found_metadata_only": "bigquery_fulltext_not_available",
    "manual_route_recommended": "manual_google_patents_recommended",
    "publication_number_format_mismatch": "publication_number_variant_mismatch",
    "found_claims": "fulltext_probe_found_claims",
    "query_error": "query_error",
  }
  return mapping.get(probe_status, "fulltext_probe_not_found")


def route_fulltext_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
  publication_number = _safe_str(candidate.get("publication_number"))
  country = _safe_str(candidate.get("country"))
  if is_us_publication(publication_number, country):
    return {
      "publication_number": publication_number,
      "route": "us_bigquery_fulltext_candidate",
      "source_route": "us_bigquery_fulltext_candidate",
      "reason": "US publication eligible for BigQuery full text route",
      "next_step": "Run dry run then explicit execute for claims/description retrieval",
    }
  return {
    "publication_number": publication_number,
    "route": "manual_fulltext_required",
    "source_route": "manual_fulltext_required",
    "reason": f"Non-US publication ({country or 'unknown'}) requires manual upload",
    "next_step": "Upload TXT/MD/CSV/XLSX via manual full text loader",
  }


def dry_run_fulltext_query(
  candidate: dict[str, Any],
  config: FullTextRetrievalConfig,
  *,
  client_factory: ClientFactory | None = None,
  scope: str | None = None,
) -> dict[str, Any]:
  publication_number = _safe_str(candidate.get("publication_number"))
  country = _safe_str(candidate.get("country"))
  fulltext_scope = validate_fulltext_scope(scope or config.fulltext_scope)
  metadata = _candidate_metadata(candidate)
  validation = validate_us_fulltext_request(publication_number, country or None, metadata=metadata)
  if not validation["ok"]:
    return {
      "dry_run_status": "error",
      "estimated_bytes": 0,
      "estimated_gb": 0.0,
      "estimated_usd": 0.0,
      "would_be_blocked_by_max_bytes": False,
      "sql": "",
      "error": validation["error"],
      "variants": validation.get("variants", []),
      "fulltext_scope": fulltext_scope,
      "cost_guard_status": "not_estimated",
      "cost_guard_reason": validation["error"],
    }
  try:
    sql = build_us_fulltext_query(
      publication_number,
      fulltext_scope,
      country=country or None,
      metadata=metadata,
    )
  except ValueError as exc:
    return {
      "dry_run_status": "error",
      "estimated_bytes": 0,
      "estimated_gb": 0.0,
      "estimated_usd": 0.0,
      "would_be_blocked_by_max_bytes": False,
      "sql": "",
      "error": str(exc),
      "variants": validation.get("variants", []),
      "fulltext_scope": fulltext_scope,
      "cost_guard_status": "not_estimated",
      "cost_guard_reason": str(exc),
    }
  resolved = resolve_project_id(config.project_id)
  project_id = resolved.get("project_id", "")
  if not project_id:
    return {
      "dry_run_status": "error",
      "estimated_bytes": 0,
      "estimated_gb": 0.0,
      "estimated_usd": 0.0,
      "would_be_blocked_by_max_bytes": False,
      "sql": sql,
      "error": resolved.get("error"),
      "fulltext_scope": fulltext_scope,
      "cost_guard_status": "not_estimated",
      "cost_guard_reason": resolved.get("error"),
    }

  factory = client_factory or _default_client_factory
  try:
    from google.cloud import bigquery

    client = factory(project_id)
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=config.use_cache)
    job = client.query(sql, job_config=job_config)
    estimated_bytes = int(job.total_bytes_processed or 0)
    estimated_usd = estimate_usd_from_bytes(estimated_bytes)
    guard = evaluate_cost_guard(estimated_bytes, estimated_usd, config)
    return {
      "dry_run_status": "ok",
      "estimated_bytes": estimated_bytes,
      "estimated_gb": bytes_to_gb(estimated_bytes),
      "estimated_usd": estimated_usd,
      "would_be_blocked_by_max_bytes": guard["cost_guard_status"] not in {"pass", "allowed_expensive_fulltext"},
      "sql": sql,
      "error": None,
      "variants": validation.get("variants", []),
      "fulltext_scope": fulltext_scope,
      **guard,
    }
  except Exception as exc:  # noqa: BLE001
    return {
      "dry_run_status": "error",
      "estimated_bytes": 0,
      "estimated_gb": 0.0,
      "estimated_usd": 0.0,
      "would_be_blocked_by_max_bytes": False,
      "sql": sql,
      "error": str(exc),
      "variants": validation.get("variants", []),
      "fulltext_scope": fulltext_scope,
      "cost_guard_status": "not_estimated",
      "cost_guard_reason": str(exc),
    }


def dry_run_scope_estimates_for_candidate(
  candidate: dict[str, Any],
  config: FullTextRetrievalConfig,
  *,
  client_factory: ClientFactory | None = None,
) -> list[dict[str, Any]]:
  rows: list[dict[str, Any]] = []
  pub = _safe_str(candidate.get("publication_number"))
  for scope in sorted(VALID_FULLTEXT_SCOPES):
    dry_run = dry_run_fulltext_query(candidate, config, client_factory=client_factory, scope=scope)
    rows.append(
      {
        "publication_number": pub,
        "scope": scope,
        "estimated_bytes": dry_run.get("estimated_bytes", 0),
        "estimated_gb": dry_run.get("estimated_gb", 0.0),
        "estimated_usd": dry_run.get("estimated_usd", 0.0),
        "cost_guard_status": dry_run.get("cost_guard_status"),
        "cost_guard_reason": dry_run.get("cost_guard_reason"),
        "dry_run_status": dry_run.get("dry_run_status"),
      },
    )
  return rows


def execute_fulltext_query(
  candidate: dict[str, Any],
  config: FullTextRetrievalConfig,
  *,
  client_factory: ClientFactory | None = None,
  estimated_bytes: int = 0,
) -> dict[str, Any]:
  if not config.execute:
    return {"execution_status": "skipped", "rows": [], "error": None}

  publication_number = _safe_str(candidate.get("publication_number"))
  country = _safe_str(candidate.get("country"))
  fulltext_scope = config.resolved_scope()
  metadata = _candidate_metadata(candidate)
  if not is_us_publication(publication_number, country):
    return {
      "execution_status": "unsupported_country",
      "rows": [],
      "error": f"Non-US publication ({country or publication_number})",
    }
  try:
    sql = build_us_fulltext_query(
      publication_number,
      fulltext_scope,
      country=country or None,
      metadata=metadata,
    )
  except ValueError as exc:
    return {"execution_status": "query_error", "rows": [], "error": str(exc)}
  resolved = resolve_project_id(config.project_id)
  project_id = resolved.get("project_id", "")
  if not project_id:
    return {"execution_status": "error", "rows": [], "error": resolved.get("error")}

  factory = client_factory or _default_client_factory
  try:
    from google.cloud import bigquery

    client = factory(project_id)
    bytes_cap = _execution_bytes_cap(config, estimated_bytes)
    job_config = bigquery.QueryJobConfig(
      dry_run=False,
      use_query_cache=config.use_cache,
      maximum_bytes_billed=bytes_cap,
    )
    query_job = client.query(sql, job_config=job_config)
    rows = [dict(row.items()) for row in query_job.result()]
    return {
      "execution_status": "executed",
      "rows": rows,
      "error": None,
      "fulltext_scope": fulltext_scope,
      "query_job": query_job,
    }
  except Exception as exc:  # noqa: BLE001
    return {"execution_status": "error", "rows": [], "error": str(exc)}


def _mark_not_found_and_cache(
  config: FullTextRetrievalConfig,
  publication_number: str,
  scope: str,
  *,
  probe_status: str,
  matched_variant: str = "",
  notes: str = "",
) -> None:
  if not config.use_not_found_cache:
    return
  mark_not_found(
    publication_number,
    scope,
    query_strategy=QUERY_STRATEGY,
    probe_status=probe_status,
    matched_variant=matched_variant,
    notes=notes,
    path=config.not_found_cache_path,
  )


def _build_fulltext_record(
  candidate: dict[str, Any],
  *,
  route: dict[str, Any],
  row: dict[str, Any] | None = None,
  coverage: dict[str, Any] | None = None,
  retrieval_status: str,
  warnings: list[str] | None = None,
  errors: list[str] | None = None,
  source_prefix: str = "bigquery_fulltext",
) -> FullTextRecord:
  row = row or {}
  claims = _safe_str(row.get("claims")) or None
  description = _safe_str(row.get("description")) or None
  examples = extract_examples(description)
  measured = extract_measured_properties("\n".join(filter(None, [claims, description, examples])))
  payload = {
    "publication_number": _safe_str(candidate.get("publication_number")),
    "title": _safe_str(row.get("title")) or candidate.get("title"),
    "assignee": _safe_str(row.get("assignee")) or candidate.get("assignee"),
    "country": _safe_str(row.get("country_code")) or candidate.get("country"),
    "url": candidate.get("url"),
    "claims": claims,
    "description": description,
    "examples": examples,
    "measured_properties": measured,
  }
  coverage = coverage or evaluate_evidence_coverage(payload)
  return FullTextRecord(
    publication_number=payload["publication_number"],
    title=payload.get("title"),
    assignee=payload.get("assignee"),
    country=payload.get("country"),
    url=payload.get("url"),
    claims=claims,
    independent_claims=detect_independent_claims(claims),
    description=description,
    examples=examples,
    measured_properties=measured,
    source_route=route.get("source_route", "unknown"),
    fulltext_source=source_prefix if claims or description else "not_fetched",
    claims_source=f"{source_prefix}" if claims else "not_fetched",
    description_source=f"{source_prefix}" if description else "not_fetched",
    examples_source=f"{source_prefix}_derived" if examples else "not_fetched",
    measured_properties_source=f"{source_prefix}_derived" if measured else "not_fetched",
    evidence_level=coverage.get("evidence_level", "metadata_only"),
    evidence_coverage=coverage,
    retrieval_status=retrieval_status,
    warnings=warnings or [],
    errors=errors or [],
  )


def retrieve_fulltext_for_candidate(
  candidate: dict[str, Any],
  config: FullTextRetrievalConfig,
  *,
  client_factory: ClientFactory | None = None,
  execute_selected: bool | None = None,
  ledger_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
  route = route_fulltext_candidate(candidate)
  publication_number = _safe_str(candidate.get("publication_number"))
  if execute_selected is not None:
    selected = bool(execute_selected)
  elif "execute_selected" in candidate:
    selected = bool(candidate.get("execute_selected"))
  else:
    selected = True
  selection_reason = str(candidate.get("execute_selection_reason") or "")

  def _finalize(
    result_status: str,
    record_dict: dict[str, Any],
    dry_run: dict[str, Any] | None,
    blocked: bool,
    cost_guard: dict[str, Any] | None = None,
  ) -> dict[str, Any]:
    enriched = _enrich_record_metadata(
      record_dict,
      execute_selected=selected,
      execute_selection_reason=selection_reason or None,
      dry_run=dry_run,
      cost_guard=cost_guard or dry_run,
      config=config,
    )
    return {
      "route": route,
      "retrieval_status": result_status,
      "record": enriched,
      "dry_run": dry_run,
      "blocked_by_cost_guard": blocked,
      "cost_guard": cost_guard or dry_run,
    }

  if route["route"] == "manual_fulltext_required":
    status = "unsupported_country" if config.execute else "manual_required"
    record = _build_fulltext_record(
      candidate,
      route=route,
      retrieval_status=status,
      warnings=["Manual full text upload required for non-US publication"],
    )
    return _finalize(status, record.to_dict(), None, False)

  if config.use_cache:
    cached = load_fulltext_from_cache(publication_number, config.cache_dir, config.resolved_scope())
    if cached:
      record = FullTextRecord.from_dict(cached)
      record.retrieval_status = "cache_hit"
      record_dict = record.to_dict()
      record_dict["fulltext_scope"] = config.resolved_scope()
      return _finalize("cache_hit", record_dict, None, False)

  if config.execute and not selected:
    record = _build_fulltext_record(
      candidate,
      route=route,
      retrieval_status="skipped_not_selected",
      warnings=["Not selected for controlled execute within limit/publication filter"],
    )
    return _finalize("skipped_not_selected", record.to_dict(), None, False)

  scope = config.resolved_scope()
  metadata = _candidate_metadata(candidate)

  if config.use_not_found_cache and is_known_not_found(
    publication_number,
    scope,
    QUERY_STRATEGY,
    path=config.not_found_cache_path,
  ):
    cache_entry = get_not_found_entry(
      publication_number,
      scope,
      QUERY_STRATEGY,
      path=config.not_found_cache_path,
    )
    record = _build_fulltext_record(
      candidate,
      route=route,
      retrieval_status="skipped_known_not_found",
      warnings=[
        "前回確認済みのため、今回は手動確認候補として扱います。",
        str((cache_entry or {}).get("notes", "")),
      ],
    )
    record_dict = record.to_dict()
    record_dict["availability_probe"] = probe_result_to_public_dict(
      FulltextAvailabilityProbeResult(
        publication_number=publication_number,
        variants_checked=build_publication_number_variants(publication_number, metadata=metadata),
        matched_variant=str((cache_entry or {}).get("matched_variant", "")),
        probe_status=str((cache_entry or {}).get("probe_status", "not_found_in_bigquery")),
        user_status_japanese="前回確認済みのため、今回は手動確認候補として扱います。",
        next_action_japanese="Google Patents / 手動貼り付けルートで確認してください。",
        scope=scope,
      ),
    )
    return _finalize("skipped_known_not_found", record_dict, None, False)

  probe_result = None
  if config.enable_availability_probe:
    probe_result = execute_availability_probe(
      publication_number,
      scope=scope,
      metadata=metadata,
      project_id=config.project_id,
      client_factory=client_factory,
      use_cache=config.use_cache,
      execute=bool(config.execute and selected),
      max_probe_usd=config.max_probe_estimated_usd,
    )
    _save_probe_artifact(probe_result, config)

    if probe_result.probe_status == "query_error" and config.execute and selected:
      record = _build_fulltext_record(
        candidate,
        route=route,
        retrieval_status="query_error",
        warnings=["Availability probe failed"],
        errors=[probe_result.query_error],
      )
      record_dict = record.to_dict()
      record_dict["availability_probe"] = probe_result_to_public_dict(probe_result)
      return _finalize("query_error", record_dict, None, False)

    if config.execute and selected and _probe_blocks_fulltext(probe_result.probe_status, scope):
      status = _retrieval_status_from_probe(probe_result.probe_status)
      _mark_not_found_and_cache(
        config,
        publication_number,
        scope,
        probe_status=probe_result.probe_status,
        matched_variant=probe_result.matched_variant,
        notes="; ".join(probe_result.internal_notes),
      )
      record = _build_fulltext_record(
        candidate,
        route=route,
        retrieval_status=status,
        warnings=[probe_result.user_status_japanese, probe_result.next_action_japanese],
      )
      record_dict = record.to_dict()
      record_dict["availability_probe"] = probe_result_to_public_dict(probe_result)
      return _finalize(status, record_dict, None, False)

  dry_run = dry_run_fulltext_query(candidate, config, client_factory=client_factory)
  guard = evaluate_cost_guard(
    int(dry_run.get("estimated_bytes", 0) or 0),
    float(dry_run.get("estimated_usd", 0.0) or 0.0),
    config,
  )
  dry_run = {**dry_run, **guard}

  policy = config.internal_cost_policy
  if policy and ledger_entries is not None:
    budget = update_remaining_budget(policy, ledger_entries)
    estimate = {
      "estimated_bytes": int(dry_run.get("estimated_bytes", 0) or 0),
      "estimated_usd": float(dry_run.get("estimated_usd", 0.0) or 0.0),
      "fulltext_scope": config.resolved_scope(),
      "cache_hit": False,
    }
    estimate_status = "dry_run_only" if not config.execute else "estimate_before_execute"
    _append_ledger_row(
      config,
      build_cost_ledger_entry_from_estimate(
        run_id=config.run_id,
        stage_id=config.stage_id,
        policy_name=policy.policy_name,
        execution_type=policy.internal_display_name,
        publication_number=publication_number,
        scope=config.resolved_scope(),
        estimated_bytes=estimate["estimated_bytes"],
        retrieval_status=estimate_status,
        raw_cost_cap_usd=policy.raw_cost_cap_usd,
        buffered_cost_cap_usd=policy.buffered_cost_cap_usd,
        remaining_raw_budget_usd=float(budget.get("remaining_raw_budget_usd", 0) or 0),
      ),
      ledger_entries,
    )
    if config.execute and selected:
      adaptive = should_execute_candidate(candidate, policy, budget, estimate)
      if not adaptive.get("allowed"):
        status = str(adaptive.get("retrieval_status") or "skipped_budget_guard")
        record = _build_fulltext_record(
          candidate,
          route=route,
          retrieval_status=status,
          warnings=[adaptive.get("public_reason", "Blocked by internal acquisition policy")],
        )
        return _finalize(status, record.to_dict(), dry_run, True, guard)

  guard_status = str(guard.get("cost_guard_status") or "")
  if guard_status == "blocked_by_usd":
    record = _build_fulltext_record(
      candidate,
      route=route,
      retrieval_status="blocked_by_usd_guard",
      warnings=["Blocked by maximum_fulltext_usd guard"],
      errors=[guard.get("cost_guard_reason", "")],
    )
    return _finalize("blocked_by_usd_guard", record.to_dict(), dry_run, True, guard)

  if guard_status == "blocked_by_gb_but_usd_allowed_requires_confirmation":
    record = _build_fulltext_record(
      candidate,
      route=route,
      retrieval_status="cost_guard_requires_expensive_confirmation",
      warnings=["GB limit exceeded but USD within budget; add --allow-expensive-fulltext"],
      errors=[guard.get("cost_guard_reason", "")],
    )
    return _finalize("cost_guard_requires_expensive_confirmation", record.to_dict(), dry_run, True, guard)

  if guard_status == "not_estimated" and dry_run.get("dry_run_status") == "error":
    record = _build_fulltext_record(
      candidate,
      route=route,
      retrieval_status="query_error",
      warnings=["Dry-run estimate failed"],
      errors=[dry_run.get("error", "estimate failed")],
    )
    return _finalize("query_error", record.to_dict(), dry_run, False, guard)

  if guard_status not in {"pass", "allowed_expensive_fulltext"} and guard_status != "not_estimated":
    record = _build_fulltext_record(
      candidate,
      route=route,
      retrieval_status="cost_guard_failed",
      warnings=["Blocked by cost guard"],
      errors=[guard.get("cost_guard_reason", "")],
    )
    return _finalize("cost_guard_failed", record.to_dict(), dry_run, True, guard)

  if config.preview_only or not config.execute:
    record = _build_fulltext_record(
      candidate,
      route=route,
      retrieval_status="dry_run_only",
      warnings=["execute=False or preview_only; dry run completed without BigQuery execution"],
    )
    record_dict = record.to_dict()
    if probe_result is not None:
      record_dict["availability_probe"] = probe_result_to_public_dict(probe_result)
    return _finalize("dry_run_only", record_dict, dry_run, False)

  if (
    config.require_fulltext_execute_confirmation
    and not config.confirm_fulltext_execute
  ):
    record = _build_fulltext_record(
      candidate,
      route=route,
      retrieval_status="execute_blocked_confirmation_required",
      warnings=["execute=True but --confirm-fulltext-execute was not provided"],
    )
    return _finalize("execute_blocked_confirmation_required", record.to_dict(), dry_run, False)

  execution = execute_fulltext_query(
    candidate,
    config,
    client_factory=client_factory,
    estimated_bytes=int(dry_run.get("estimated_bytes", 0) or 0),
  )
  if execution.get("execution_status") == "unsupported_country":
    record = _build_fulltext_record(
      candidate,
      route=route,
      retrieval_status="unsupported_country",
      warnings=["Non-US publication cannot be executed via BigQuery fulltext"],
      errors=[execution.get("error")] if execution.get("error") else [],
    )
    return _finalize("unsupported_country", record.to_dict(), dry_run, False)

  if execution.get("execution_status") in {"error", "query_error"}:
    record = _build_fulltext_record(
      candidate,
      route=route,
      retrieval_status="query_error",
      warnings=["BigQuery fulltext query failed"],
      errors=[execution.get("error")] if execution.get("error") else [],
    )
    return _finalize("query_error", record.to_dict(), dry_run, False)

  if policy and ledger_entries is not None and execution.get("execution_status") == "executed":
    budget = update_remaining_budget(policy, ledger_entries)
    _append_ledger_row(
      config,
      build_cost_ledger_entry_from_bigquery_job(
        run_id=config.run_id,
        stage_id=config.stage_id,
        policy_name=policy.policy_name,
        execution_type=policy.internal_display_name,
        publication_number=publication_number,
        scope=config.resolved_scope(),
        job=execution.get("query_job"),
        estimated_bytes=int(dry_run.get("estimated_bytes", 0) or 0),
        retrieval_status="actual_cost_recorded",
        raw_cost_cap_usd=policy.raw_cost_cap_usd,
        buffered_cost_cap_usd=policy.buffered_cost_cap_usd,
        remaining_raw_budget_usd=float(budget.get("remaining_raw_budget_usd", 0) or 0),
      ),
      ledger_entries,
    )

  row = execution["rows"][0] if execution.get("rows") else {}
  claims_text = _safe_str(row.get("claims"))
  description_text = _safe_str(row.get("description"))
  expensive = guard_status == "allowed_expensive_fulltext"
  retrieval_status = "retrieved" if row else "not_found"
  if row and expensive:
    retrieval_status = "allowed_expensive_execute"
  if row and scope == "claims_only" and not claims_text:
    retrieval_status = "bigquery_fulltext_not_available"
  elif row and scope == "description_only" and not description_text:
    retrieval_status = "bigquery_fulltext_not_available"
  elif not row:
    retrieval_status = "not_found"

  if retrieval_status in {"not_found", "bigquery_fulltext_not_available"}:
    _mark_not_found_and_cache(
      config,
      publication_number,
      scope,
      probe_status="not_found_in_bigquery",
      matched_variant=str(row.get("publication_number") or ""),
      notes="Fulltext query returned no usable text",
    )

  record = _build_fulltext_record(
    candidate,
    route=route,
    row=row,
    retrieval_status=retrieval_status,
    warnings=(
      []
      if retrieval_status in {"retrieved", "allowed_expensive_execute"}
      else [
        probe_result.user_status_japanese if probe_result else "",
        "BigQuery側では請求項が確認できませんでした。Google Patents / PDF / 手動貼り付けルートで確認してください。",
      ]
    ),
    errors=[],
  )
  record_dict = record.to_dict()
  record_dict["fulltext_scope"] = scope
  if probe_result is not None:
    record_dict["availability_probe"] = probe_result_to_public_dict(probe_result)
  if retrieval_status in {"retrieved", "allowed_expensive_execute"}:
    save_fulltext_to_cache(record_dict, config.cache_dir, scope)
  elif retrieval_status in {"not_found", "bigquery_fulltext_not_available"}:
    record_dict["manual_route_recommended"] = True
  return _finalize(retrieval_status, record_dict, dry_run, False, guard)


def retrieve_fulltext_for_top_candidates(
  candidates: list[dict[str, Any]],
  config: FullTextRetrievalConfig,
  *,
  client_factory: ClientFactory | None = None,
) -> dict[str, Any]:
  warnings: list[str] = []
  errors: list[str] = []
  retrieved_records: list[dict[str, Any]] = []
  manual_required_records: list[dict[str, Any]] = []
  cache_hits = 0
  cache_misses = 0
  blocked_by_cost_guard = 0
  us_fulltext_candidates = 0
  total_estimated_bytes = 0

  for candidate in candidates:
    route = route_fulltext_candidate(candidate)
    if route["route"] == "us_bigquery_fulltext_candidate":
      us_fulltext_candidates += 1

    result = retrieve_fulltext_for_candidate(
      candidate,
      config,
      client_factory=client_factory,
    )
    status = result.get("retrieval_status")
    if status == "cache_hit":
      cache_hits += 1
    elif status != "manual_required":
      cache_misses += 1
    if result.get("dry_run"):
      total_estimated_bytes += int(result["dry_run"].get("estimated_bytes", 0))
    status = result.get("retrieval_status")
    if status == "manual_required":
      manual_required_records.append(result["record"])
    elif status == "blocked_by_cost_guard" or status == "cost_guard_failed":
      blocked_by_cost_guard += 1
      retrieved_records.append(result["record"])
    else:
      retrieved_records.append(result["record"])
    if result["record"].get("errors"):
      errors.extend(result["record"]["errors"])

  return {
    "status": "ok" if not errors else "error",
    "mode": "execute" if config.execute else "dry_run",
    "total_candidates": len(candidates),
    "us_fulltext_candidates": us_fulltext_candidates,
    "manual_required_candidates": len(manual_required_records),
    "cache_hits": cache_hits,
    "cache_misses": cache_misses,
    "blocked_by_cost_guard": blocked_by_cost_guard,
    "cost_guard_failed_count": blocked_by_cost_guard,
    "total_estimated_bytes": total_estimated_bytes,
    "total_estimated_gb": bytes_to_gb(total_estimated_bytes),
    "total_estimated_usd": estimate_usd_from_bytes(total_estimated_bytes),
    "maximum_bytes_billed_gb": config.maximum_bytes_billed_gb,
    "retrieved_records": retrieved_records,
    "manual_required_records": manual_required_records,
    "warnings": warnings,
    "errors": errors,
  }


def _count_evidence_levels(records: list[dict[str, Any]]) -> dict[str, int]:
  counts = {
    "high_fulltext_evidence_count": 0,
    "medium_fulltext_evidence_count": 0,
    "low_fulltext_evidence_count": 0,
    "metadata_only_count": 0,
  }
  for record in records:
    level = str(record.get("evidence_level", "metadata_only"))
    if level == "high_fulltext_evidence":
      counts["high_fulltext_evidence_count"] += 1
    elif level == "medium_fulltext_evidence":
      counts["medium_fulltext_evidence_count"] += 1
    elif level == "low_fulltext_evidence":
      counts["low_fulltext_evidence_count"] += 1
    else:
      counts["metadata_only_count"] += 1
  return counts


def retrieve_controlled_fulltext_run(
  top5_candidates: list[dict[str, Any]],
  config: FullTextRetrievalConfig,
  strategic_watch_candidates: list[dict[str, Any]] | None = None,
  *,
  client_factory: ClientFactory | None = None,
) -> dict[str, Any]:
  plan = build_controlled_fulltext_plan(
    top5_candidates,
    strategic_watch_candidates,
    execute=config.execute,
    fulltext_scope=config.resolved_scope(),
  )
  selected_targets = select_fulltext_execute_targets(
    plan,
    limit=config.execute_limit,
    publication_number=config.publication_number,
    execute_top_n=config.execute_top_n,
  )
  plan = mark_execute_selected_targets(plan, selected_targets)

  if config.publication_number and not selected_targets:
    pub_norm = _normalize_publication_number(config.publication_number)
    non_us_match = any(
      _normalize_publication_number(str(row.get("publication_number", ""))) == pub_norm
      for row in plan.get("manual_required_candidates", [])
      + plan.get("strategic_watch_manual_candidates", [])
    )
    if non_us_match:
      warnings_pub = [f"Publication {config.publication_number} is manual route (non-US); not executed."]
    else:
      warnings_pub = [f"Publication {config.publication_number} not found in US fulltext targets."]
  else:
    warnings_pub = []

  dry_run_by_pub: dict[str, dict[str, Any]] = {}
  scope_estimates: list[dict[str, Any]] = []
  estimates_by_pub: dict[str, dict[str, Any]] = {}
  for candidate in plan["fulltext_targets"]:
    pub_norm = _normalize_publication_number(str(candidate.get("publication_number", "")))
    dry_run_by_pub[pub_norm] = dry_run_fulltext_query(
      candidate,
      config,
      client_factory=client_factory,
      scope=config.resolved_scope(),
    )
    estimates_by_pub[pub_norm] = {
      "estimated_bytes": int(dry_run_by_pub[pub_norm].get("estimated_bytes", 0) or 0),
      "estimated_usd": float(dry_run_by_pub[pub_norm].get("estimated_usd", 0.0) or 0.0),
      "fulltext_scope": config.resolved_scope(),
    }
    scope_estimates.extend(
      dry_run_scope_estimates_for_candidate(candidate, config, client_factory=client_factory),
    )

  policy = config.internal_cost_policy
  ledger_entries: list[dict[str, Any]] = []
  adaptive_plan = build_adaptive_retrieval_plan(
    plan["fulltext_targets"],
    policy,
    estimates=estimates_by_pub,
  ) if policy else {}

  execute_preview = build_fulltext_execute_preview(
    plan,
    execute=config.execute,
    confirm_fulltext_execute=config.confirm_fulltext_execute,
    require_confirmation=config.require_fulltext_execute_confirmation,
    publication_number_filter=config.publication_number,
    execute_limit=config.execute_limit,
    selected_targets=selected_targets,
    dry_run_by_pub=dry_run_by_pub,
    scope_estimates=scope_estimates,
    fulltext_scope=config.resolved_scope(),
    maximum_fulltext_gb=config.maximum_bytes_billed_gb,
    maximum_fulltext_usd=config.maximum_fulltext_usd,
    allow_expensive_fulltext=config.allow_expensive_fulltext,
  )

  warnings: list[str] = list(warnings_pub)
  errors: list[str] = []
  retrieved_records: list[dict[str, Any]] = []
  cache_hits = 0
  dry_run_only_count = 0
  retrieved_count = 0
  blocked_by_cost_guard = 0
  cost_guard_requires_expensive_count = 0
  blocked_by_usd_count = 0
  skipped_not_selected_count = 0
  execute_blocked_count = 0
  total_estimated_bytes = 0

  effective_config = config
  if config.preview_only:
    effective_config = FullTextRetrievalConfig(
      project_id=config.project_id,
      dry_run=True,
      execute=False,
      maximum_bytes_billed_gb=config.maximum_bytes_billed_gb,
      output_dir=config.output_dir,
      cache_dir=config.cache_dir,
      use_cache=config.use_cache,
      allow_manual_fallback=config.allow_manual_fallback,
      execute_limit=config.execute_limit,
      publication_number=config.publication_number,
      execute_top_n=config.execute_top_n,
      confirm_fulltext_execute=config.confirm_fulltext_execute,
      require_fulltext_execute_confirmation=config.require_fulltext_execute_confirmation,
      preview_only=False,
      fulltext_scope=config.fulltext_scope,
      maximum_fulltext_usd=config.maximum_fulltext_usd,
      allow_expensive_fulltext=config.allow_expensive_fulltext,
      internal_cost_policy=config.internal_cost_policy,
      enable_cost_ledger=config.enable_cost_ledger,
      global_ledger_path=config.global_ledger_path,
      run_id=config.run_id,
      stage_id=config.stage_id,
    )
  elif policy and not policy.fulltext_enabled:
    effective_config = FullTextRetrievalConfig(
      project_id=config.project_id,
      dry_run=True,
      execute=False,
      maximum_bytes_billed_gb=config.maximum_bytes_billed_gb,
      output_dir=config.output_dir,
      cache_dir=config.cache_dir,
      use_cache=config.use_cache,
      allow_manual_fallback=config.allow_manual_fallback,
      execute_limit=config.execute_limit,
      publication_number=config.publication_number,
      execute_top_n=config.execute_top_n,
      confirm_fulltext_execute=config.confirm_fulltext_execute,
      require_fulltext_execute_confirmation=config.require_fulltext_execute_confirmation,
      preview_only=False,
      fulltext_scope=config.fulltext_scope,
      maximum_fulltext_usd=policy.raw_cost_cap_usd,
      allow_expensive_fulltext=config.allow_expensive_fulltext,
      internal_cost_policy=policy,
      enable_cost_ledger=config.enable_cost_ledger,
      global_ledger_path=config.global_ledger_path,
      run_id=config.run_id,
      stage_id=config.stage_id,
    )

  for candidate in plan["fulltext_targets"]:
    result = retrieve_fulltext_for_candidate(
      candidate,
      effective_config,
      client_factory=client_factory,
      ledger_entries=ledger_entries,
    )
    status = str(result.get("retrieval_status", ""))
    if status == "cache_hit":
      cache_hits += 1
      retrieved_count += 1
    elif status == "dry_run_only":
      dry_run_only_count += 1
    elif status == "retrieved":
      retrieved_count += 1
    elif status == "skipped_not_selected":
      skipped_not_selected_count += 1
    elif status == "execute_blocked_confirmation_required":
      execute_blocked_count += 1
    elif status in {"cost_guard_failed", "blocked_by_cost_guard"}:
      blocked_by_cost_guard += 1
    elif status == "cost_guard_requires_expensive_confirmation":
      cost_guard_requires_expensive_count += 1
      blocked_by_cost_guard += 1
    elif status == "blocked_by_usd_guard":
      blocked_by_usd_count += 1
      blocked_by_cost_guard += 1
    elif status in {"skipped_budget_guard", "skipped_internal_cost_policy", "skipped_policy_scope"}:
      skipped_not_selected_count += 1
    if result.get("dry_run"):
      total_estimated_bytes += int(result["dry_run"].get("estimated_bytes", 0))
    retrieved_records.append(result["record"])
    if result["record"].get("errors"):
      errors.extend(result["record"]["errors"])

  manual_rows = list(plan["manual_required_candidates"])
  strategic_rows = list(plan["strategic_watch_manual_candidates"])
  evidence_counts = _count_evidence_levels(retrieved_records)
  execute_results = build_fulltext_execute_results_rows(retrieved_records)

  summary = {
    "status": "ok" if not errors else "error",
    "mode": "execute" if config.execute and not config.preview_only else "dry_run",
    "execute_requested": bool(config.execute),
    "confirm_fulltext_execute": bool(config.confirm_fulltext_execute),
    "execute_limit": config.execute_limit,
    "publication_number_filter": config.publication_number,
    "execute_selected_count": len(selected_targets),
    "total_top5_candidates": len(top5_candidates),
    "total_candidates": len(top5_candidates),
    "us_fulltext_targets": len(plan["fulltext_targets"]),
    "us_fulltext_candidates": len(plan["fulltext_targets"]),
    "retrieved_count": retrieved_count,
    "cache_hit_count": cache_hits,
    "cache_hits": cache_hits,
    "dry_run_only_count": dry_run_only_count,
    "skipped_not_selected_count": skipped_not_selected_count,
    "execute_blocked_confirmation_required_count": execute_blocked_count,
    "manual_required_count": len(manual_rows),
    "manual_required_candidates": len(manual_rows) + len(strategic_rows),
    "strategic_watch_manual_count": len(strategic_rows),
    "blocked_by_cost_guard": blocked_by_cost_guard,
    "cost_guard_failed_count": blocked_by_cost_guard,
    "cost_guard_requires_expensive_count": cost_guard_requires_expensive_count,
    "blocked_by_usd_count": blocked_by_usd_count,
    "cost_guard_status": "failed" if blocked_by_cost_guard else "ok",
    "fulltext_scope": config.resolved_scope(),
    "maximum_fulltext_usd": config.maximum_fulltext_usd,
    "allow_expensive_fulltext": config.allow_expensive_fulltext,
    "total_estimated_bytes": total_estimated_bytes,
    "total_estimated_gb": bytes_to_gb(total_estimated_bytes),
    "total_estimated_usd": estimate_usd_from_bytes(total_estimated_bytes),
    "maximum_bytes_billed_gb": config.maximum_bytes_billed_gb,
    "warnings": warnings + [plan["plan_summary"].get("caveat_japanese", "")],
    "errors": errors,
    **evidence_counts,
  }

  ledger_summary = summarize_cost_ledger(ledger_entries)
  public_cost_status: dict[str, Any] = {}
  if policy:
    public_cost_status = build_public_cost_status(
      ledger_summary,
      CostVisibilityPolicy(),
      policy_summary=adaptive_plan.get("public_policy_summary"),
      stop_reason_internal=adaptive_plan.get("internal_stop_reason"),
    )

  return {
    **summary,
    "plan": plan,
    "adaptive_plan": adaptive_plan,
    "ledger_entries": ledger_entries,
    "ledger_summary": ledger_summary,
    "public_cost_status": public_cost_status,
    "internal_cost_policy_name": policy.policy_name if policy else None,
    "execute_preview": execute_preview,
    "execute_results": execute_results,
    "retrieved_records": retrieved_records,
    "manual_required_records": manual_rows + strategic_rows,
    "manual_required_rows": manual_rows,
    "strategic_watch_manual_rows": strategic_rows,
    "checklist_markdown": render_manual_fulltext_checklist(plan),
    "summary": summary,
  }


def save_fulltext_collection_results(
  records: list[dict[str, Any]],
  output_dir: str,
  *,
  summary: dict[str, Any] | None = None,
  manual_records: list[dict[str, Any]] | None = None,
  markdown: str | None = None,
) -> dict[str, str]:
  out = build_output_directory(output_dir)
  paths = {
    "top5_fulltext_records_json": str(out / "top5_fulltext_records.json"),
    "top5_fulltext_records_csv": save_records_csv(records, out / "top5_fulltext_records.csv"),
    "manual_fulltext_required_csv": save_records_csv(
      manual_records or [],
      out / "manual_fulltext_required.csv",
    ),
    "fulltext_retrieval_summary_json": save_retrieval_summary(
      summary or {},
      out / "fulltext_retrieval_summary.json",
    ),
  }
  with Path(paths["top5_fulltext_records_json"]).open("w", encoding="utf-8") as handle:
    json.dump(records, handle, indent=2, ensure_ascii=False)
  if markdown:
    report_path = out / "fulltext_evidence_report.md"
    report_path.write_text(markdown, encoding="utf-8")
    paths["fulltext_evidence_report_md"] = str(report_path)
  paths["output_dir"] = str(out)
  return paths
