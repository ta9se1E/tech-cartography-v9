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
  build_controlled_fulltext_plan,
  render_manual_fulltext_checklist,
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

  def maximum_bytes_billed(self) -> int:
    return gb_to_bytes(self.maximum_bytes_billed_gb)


def _default_client_factory(project_id: str) -> Any:
  from google.cloud import bigquery

  return bigquery.Client(project=project_id)


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
) -> dict[str, Any]:
  route = route_fulltext_candidate(candidate)
  publication_number = _safe_str(candidate.get("publication_number"))

  if route["route"] == "manual_fulltext_required":
    status = "unsupported_country" if config.execute else "manual_required"
    record = _build_fulltext_record(
      candidate,
      route=route,
      retrieval_status=status,
      warnings=["Manual full text upload required for non-US publication"],
    )
    return {
      "route": route,
      "retrieval_status": status,
      "record": record.to_dict(),
      "dry_run": None,
      "blocked_by_cost_guard": False,
    }

  if config.use_cache:
    cached = load_fulltext_from_cache(publication_number, config.cache_dir)
    if cached:
      record = FullTextRecord.from_dict(cached)
      record.retrieval_status = "cache_hit"
      return {
        "route": route,
        "retrieval_status": "cache_hit",
        "record": record.to_dict(),
        "dry_run": None,
        "blocked_by_cost_guard": False,
      }

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
    return {
      "route": route,
      "retrieval_status": "cost_guard_failed",
      "record": record.to_dict(),
      "dry_run": dry_run,
      "blocked_by_cost_guard": True,
    }

  if not config.execute:
    record = _build_fulltext_record(
      candidate,
      route=route,
      retrieval_status="dry_run_only",
      warnings=["execute=False; dry run completed without BigQuery execution"],
    )
    return {
      "route": route,
      "retrieval_status": "dry_run_only",
      "record": record.to_dict(),
      "dry_run": dry_run,
      "blocked_by_cost_guard": False,
    }

  execution = execute_fulltext_query(candidate, config, client_factory=client_factory)
  if execution.get("execution_status") == "unsupported_country":
    record = _build_fulltext_record(
      candidate,
      route=route,
      retrieval_status="unsupported_country",
      warnings=["Non-US publication cannot be executed via BigQuery fulltext"],
      errors=[execution.get("error")] if execution.get("error") else [],
    )
    return {
      "route": route,
      "retrieval_status": "unsupported_country",
      "record": record.to_dict(),
      "dry_run": dry_run,
      "blocked_by_cost_guard": False,
    }

  if execution.get("execution_status") == "error" or execution.get("execution_status") == "query_error":
    record = _build_fulltext_record(
      candidate,
      route=route,
      retrieval_status="query_error",
      warnings=["BigQuery fulltext query failed"],
      errors=[execution.get("error")] if execution.get("error") else [],
    )
    return {
      "route": route,
      "retrieval_status": "query_error",
      "record": record.to_dict(),
      "dry_run": dry_run,
      "blocked_by_cost_guard": False,
    }

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
  return {
    "route": route,
    "retrieval_status": record.retrieval_status,
    "record": record.to_dict(),
    "dry_run": dry_run,
    "blocked_by_cost_guard": False,
  }


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
  warnings: list[str] = []
  errors: list[str] = []
  retrieved_records: list[dict[str, Any]] = []
  cache_hits = 0
  dry_run_only_count = 0
  retrieved_count = 0
  blocked_by_cost_guard = 0
  total_estimated_bytes = 0

  for candidate in plan["fulltext_targets"]:
    result = retrieve_fulltext_for_candidate(
      candidate,
      config,
      client_factory=client_factory,
    )
    status = str(result.get("retrieval_status", ""))
    if status == "cache_hit":
      cache_hits += 1
    elif status == "dry_run_only":
      dry_run_only_count += 1
    elif status == "retrieved":
      retrieved_count += 1
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

  summary = {
    "status": "ok" if not errors else "error",
    "mode": "execute" if config.execute else "dry_run",
    "total_top5_candidates": len(top5_candidates),
    "total_candidates": len(top5_candidates),
    "us_fulltext_targets": len(plan["fulltext_targets"]),
    "us_fulltext_candidates": len(plan["fulltext_targets"]),
    "retrieved_count": retrieved_count,
    "cache_hit_count": cache_hits,
    "cache_hits": cache_hits,
    "dry_run_only_count": dry_run_only_count,
    "manual_required_count": len(manual_rows),
    "manual_required_candidates": len(manual_rows) + len(strategic_rows),
    "strategic_watch_manual_count": len(strategic_rows),
    "blocked_by_cost_guard": blocked_by_cost_guard,
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
