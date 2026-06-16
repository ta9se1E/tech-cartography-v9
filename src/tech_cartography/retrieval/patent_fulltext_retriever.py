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
)
from tech_cartography.retrieval.bigquery_fulltext_query_builder import (
  build_us_fulltext_query,
  is_us_publication,
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

  def maximum_bytes_billed(self) -> int:
    return gb_to_bytes(self.maximum_bytes_billed_gb)


def _default_client_factory(project_id: str) -> Any:
  from google.cloud import bigquery

  return bigquery.Client(project=project_id)


def _enrich_record_metadata(
  record: dict[str, Any],
  *,
  execute_selected: bool | None = None,
  execute_selection_reason: str | None = None,
  dry_run: dict[str, Any] | None = None,
) -> dict[str, Any]:
  enriched = dict(record)
  if execute_selected is not None:
    enriched["execute_selected"] = execute_selected
  if execute_selection_reason:
    enriched["execute_selection_reason"] = execute_selection_reason
  if dry_run:
    enriched["estimated_bytes"] = dry_run.get("estimated_bytes", 0)
    enriched["estimated_gb"] = dry_run.get("estimated_gb", 0.0)
    enriched["estimated_usd"] = dry_run.get("estimated_usd", 0.0)
    enriched["cost_guard_status"] = (
      "failed" if dry_run.get("would_be_blocked_by_max_bytes") else "ok"
    )
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
) -> dict[str, Any]:
  publication_number = _safe_str(candidate.get("publication_number"))
  country = _safe_str(candidate.get("country"))
  validation = validate_us_fulltext_request(publication_number, country or None)
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
    }
  try:
    sql = build_us_fulltext_query(publication_number, country=country or None)
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
    }

  factory = client_factory or _default_client_factory
  try:
    from google.cloud import bigquery

    client = factory(project_id)
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=config.use_cache)
    job = client.query(sql, job_config=job_config)
    estimated_bytes = int(job.total_bytes_processed or 0)
    return {
      "dry_run_status": "ok",
      "estimated_bytes": estimated_bytes,
      "estimated_gb": bytes_to_gb(estimated_bytes),
      "estimated_usd": estimate_usd_from_bytes(estimated_bytes),
      "would_be_blocked_by_max_bytes": estimated_bytes > config.maximum_bytes_billed(),
      "sql": sql,
      "error": None,
      "variants": validation.get("variants", []),
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
    }


def execute_fulltext_query(
  candidate: dict[str, Any],
  config: FullTextRetrievalConfig,
  *,
  client_factory: ClientFactory | None = None,
) -> dict[str, Any]:
  if not config.execute:
    return {"execution_status": "skipped", "rows": [], "error": None}

  publication_number = _safe_str(candidate.get("publication_number"))
  country = _safe_str(candidate.get("country"))
  if not is_us_publication(publication_number, country):
    return {
      "execution_status": "unsupported_country",
      "rows": [],
      "error": f"Non-US publication ({country or publication_number})",
    }
  try:
    sql = build_us_fulltext_query(publication_number, country=country or None)
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
    job_config = bigquery.QueryJobConfig(
      dry_run=False,
      use_query_cache=config.use_cache,
      maximum_bytes_billed=config.maximum_bytes_billed(),
    )
    rows = [dict(row.items()) for row in client.query(sql, job_config=job_config).result()]
    return {"execution_status": "executed", "rows": rows, "error": None}
  except Exception as exc:  # noqa: BLE001
    return {"execution_status": "error", "rows": [], "error": str(exc)}


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

  def _finalize(result_status: str, record_dict: dict[str, Any], dry_run: dict[str, Any] | None, blocked: bool) -> dict[str, Any]:
    enriched = _enrich_record_metadata(
      record_dict,
      execute_selected=selected,
      execute_selection_reason=selection_reason or None,
      dry_run=dry_run,
    )
    return {
      "route": route,
      "retrieval_status": result_status,
      "record": enriched,
      "dry_run": dry_run,
      "blocked_by_cost_guard": blocked,
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
    cached = load_fulltext_from_cache(publication_number, config.cache_dir)
    if cached:
      record = FullTextRecord.from_dict(cached)
      record.retrieval_status = "cache_hit"
      return _finalize("cache_hit", record.to_dict(), None, False)

  if config.execute and not selected:
    record = _build_fulltext_record(
      candidate,
      route=route,
      retrieval_status="skipped_not_selected",
      warnings=["Not selected for controlled execute within limit/publication filter"],
    )
    return _finalize("skipped_not_selected", record.to_dict(), None, False)

  dry_run = dry_run_fulltext_query(candidate, config, client_factory=client_factory)
  blocked = bool(dry_run.get("would_be_blocked_by_max_bytes"))
  if blocked:
    record = _build_fulltext_record(
      candidate,
      route=route,
      retrieval_status="cost_guard_failed",
      warnings=["Blocked by maximum_bytes_billed guard"],
      errors=[f"estimated_bytes={dry_run.get('estimated_bytes')}"],
    )
    return _finalize("cost_guard_failed", record.to_dict(), dry_run, True)

  if config.preview_only or not config.execute:
    record = _build_fulltext_record(
      candidate,
      route=route,
      retrieval_status="dry_run_only",
      warnings=["execute=False or preview_only; dry run completed without BigQuery execution"],
    )
    return _finalize("dry_run_only", record.to_dict(), dry_run, False)

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

  execution = execute_fulltext_query(candidate, config, client_factory=client_factory)
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

  row = execution["rows"][0] if execution.get("rows") else {}
  retrieval_status = "retrieved" if row else "not_found"
  record = _build_fulltext_record(
    candidate,
    route=route,
    row=row,
    retrieval_status=retrieval_status,
    warnings=[] if row else ["No full text rows returned from BigQuery"],
    errors=[],
  )
  if retrieval_status == "retrieved":
    save_fulltext_to_cache(record.to_dict(), config.cache_dir)
  return _finalize(record.retrieval_status, record.to_dict(), dry_run, False)


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
  for candidate in plan["fulltext_targets"]:
    pub_norm = _normalize_publication_number(str(candidate.get("publication_number", "")))
    dry_run_by_pub[pub_norm] = dry_run_fulltext_query(candidate, config, client_factory=client_factory)

  execute_preview = build_fulltext_execute_preview(
    plan,
    execute=config.execute,
    confirm_fulltext_execute=config.confirm_fulltext_execute,
    require_confirmation=config.require_fulltext_execute_confirmation,
    publication_number_filter=config.publication_number,
    execute_limit=config.execute_limit,
    selected_targets=selected_targets,
    dry_run_by_pub=dry_run_by_pub,
  )

  warnings: list[str] = list(warnings_pub)
  errors: list[str] = []
  retrieved_records: list[dict[str, Any]] = []
  cache_hits = 0
  dry_run_only_count = 0
  retrieved_count = 0
  blocked_by_cost_guard = 0
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
    )

  for candidate in plan["fulltext_targets"]:
    result = retrieve_fulltext_for_candidate(
      candidate,
      effective_config,
      client_factory=client_factory,
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
    "cost_guard_status": "failed" if blocked_by_cost_guard else "ok",
    "total_estimated_bytes": total_estimated_bytes,
    "total_estimated_gb": bytes_to_gb(total_estimated_bytes),
    "total_estimated_usd": estimate_usd_from_bytes(total_estimated_bytes),
    "maximum_bytes_billed_gb": config.maximum_bytes_billed_gb,
    "warnings": warnings + [plan["plan_summary"].get("caveat_japanese", "")],
    "errors": errors,
    **evidence_counts,
  }

  return {
    **summary,
    "plan": plan,
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
