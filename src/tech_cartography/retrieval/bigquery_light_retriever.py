"""BigQuery light multi-query retriever for v7."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from tech_cartography.curation.dedup import deduplicate_patent_records
from tech_cartography.reports.project_export import (
  build_output_directory,
  save_records_csv,
  save_retrieval_summary,
)
from tech_cartography.retrieval.bigquery_env import (
  bytes_to_gb,
  check_bigquery_environment,
  estimate_usd_from_bytes,
  gb_to_bytes,
  resolve_project_id,
)
from tech_cartography.retrieval.bigquery_query_builder import (
  build_lightweight_patent_query,
  infer_matched_terms,
)
from tech_cartography.strategy.query_plan import QueryPlan

ClientFactory = Callable[[str], Any]


@dataclass
class RetrievalConfig:
  project_id: str | None = None
  dry_run: bool = True
  execute: bool = False
  maximum_bytes_billed_gb: float = 50.0
  max_results_per_intent: int = 500
  max_results_total: int = 2000
  output_dir: str = "outputs/bigquery_light_retrieval"
  use_cache: bool = True

  def maximum_bytes_billed(self) -> int:
    return gb_to_bytes(self.maximum_bytes_billed_gb)


def _default_client_factory(project_id: str) -> Any:
  from google.cloud import bigquery

  return bigquery.Client(project=project_id)


def _resolve_output_dir(config: RetrievalConfig) -> Path:
  base = Path(config.output_dir)
  if base.name and not base.exists() and "{" not in str(base):
    return build_output_directory(base)
  if base.exists() and any(base.iterdir()):
    return base
  return build_output_directory(base)


def _row_to_dict(row: Any) -> dict[str, Any]:
  if isinstance(row, dict):
    return dict(row)
  return dict(row.items())


def dry_run_query(
  sql: str,
  config: RetrievalConfig,
  *,
  client_factory: ClientFactory | None = None,
) -> dict[str, Any]:
  resolved = resolve_project_id(config.project_id)
  project_id = resolved.get("project_id", "")
  if not project_id:
    return {
      "dry_run_status": "error",
      "estimated_bytes": 0,
      "estimated_gb": 0.0,
      "estimated_usd": 0.0,
      "would_be_blocked_by_max_bytes": False,
      "error": resolved.get("error") or "project_id unresolved",
    }

  factory = client_factory or _default_client_factory
  try:
    from google.cloud import bigquery

    client = factory(project_id)
    job_config = bigquery.QueryJobConfig(
      dry_run=True,
      use_query_cache=config.use_cache,
    )
    job = client.query(sql, job_config=job_config)
    estimated_bytes = int(job.total_bytes_processed or 0)
    would_block = estimated_bytes > config.maximum_bytes_billed()
    return {
      "dry_run_status": "ok",
      "estimated_bytes": estimated_bytes,
      "estimated_gb": bytes_to_gb(estimated_bytes),
      "estimated_usd": estimate_usd_from_bytes(estimated_bytes),
      "would_be_blocked_by_max_bytes": would_block,
      "project_id": project_id,
      "error": None,
    }
  except Exception as exc:  # noqa: BLE001
    return {
      "dry_run_status": "error",
      "estimated_bytes": 0,
      "estimated_gb": 0.0,
      "estimated_usd": 0.0,
      "would_be_blocked_by_max_bytes": False,
      "error": str(exc),
    }


def execute_query(
  sql: str,
  config: RetrievalConfig,
  *,
  client_factory: ClientFactory | None = None,
) -> list[dict]:
  if not config.execute:
    return []

  resolved = resolve_project_id(config.project_id)
  project_id = resolved.get("project_id", "")
  if not project_id:
    raise RuntimeError(resolved.get("error") or "project_id unresolved")

  factory = client_factory or _default_client_factory
  from google.cloud import bigquery

  client = factory(project_id)
  job_config = bigquery.QueryJobConfig(
    dry_run=False,
    use_query_cache=config.use_cache,
    maximum_bytes_billed=config.maximum_bytes_billed(),
  )
  rows = client.query(sql, job_config=job_config).result()
  return [_row_to_dict(row) for row in rows]


def _annotate_records(
  records: list[dict],
  query_plan: QueryPlan,
) -> list[dict]:
  annotated: list[dict] = []
  for record in records:
    row = dict(record)
    row["search_intent"] = query_plan.intent_id
    row["query_plan_id"] = query_plan.intent_id
    row["query_hint"] = query_plan.query_hint
    row["matched_terms"] = infer_matched_terms(row, query_plan)
    row.setdefault("source_type", "bigquery_lightweight")
    row.setdefault("evidence_level", "metadata_only")
    row.setdefault("claims_source", "not_fetched")
    row.setdefault("description_source", "not_fetched")
    annotated.append(row)
  return annotated


def run_query_plan(
  query_plan: QueryPlan,
  config: RetrievalConfig,
  *,
  limit: int | None = None,
  client_factory: ClientFactory | None = None,
) -> dict[str, Any]:
  resolved_limit = limit or min(config.max_results_per_intent, query_plan.max_results)
  sql = build_lightweight_patent_query(query_plan, limit=resolved_limit)
  dry_run_result = dry_run_query(sql, config, client_factory=client_factory)

  execution_status = "skipped"
  records: list[dict] = []
  error = dry_run_result.get("error")

  if (
    config.execute
    and dry_run_result.get("dry_run_status") == "ok"
    and not dry_run_result.get("would_be_blocked_by_max_bytes")
  ):
    try:
      records = execute_query(sql, config, client_factory=client_factory)
      records = _annotate_records(records, query_plan)
      execution_status = "executed"
    except Exception as exc:  # noqa: BLE001
      execution_status = "error"
      error = str(exc)
  elif config.execute and dry_run_result.get("would_be_blocked_by_max_bytes"):
    execution_status = "blocked_by_max_bytes"

  return {
    "intent_id": query_plan.intent_id,
    "purpose": query_plan.purpose,
    "sql": sql,
    "dry_run_status": dry_run_result.get("dry_run_status"),
    "estimated_bytes": dry_run_result.get("estimated_bytes", 0),
    "estimated_gb": dry_run_result.get("estimated_gb", 0.0),
    "estimated_usd": dry_run_result.get("estimated_usd", 0.0),
    "would_be_blocked_by_max_bytes": dry_run_result.get(
      "would_be_blocked_by_max_bytes",
      False,
    ),
    "execution_status": execution_status,
    "record_count": len(records),
    "records": records,
    "output_preview": records[:3],
    "error": error,
  }


def save_retrieval_results(
  records: list[dict],
  output_dir: str,
  filename: str = "bigquery_light_results.csv",
) -> str:
  path = Path(output_dir) / filename
  return save_records_csv(records, path)


def load_cached_results(path: str) -> list[dict]:
  csv_path = Path(path)
  if not csv_path.exists():
    return []
  with csv_path.open(encoding="utf-8", newline="") as handle:
    return list(csv.DictReader(handle))


def run_multi_query_retrieval(
  query_plans: list[QueryPlan],
  config: RetrievalConfig,
  *,
  client_factory: ClientFactory | None = None,
) -> dict[str, Any]:
  """Run dry-run and optional execute for each query plan."""
  output_dir = _resolve_output_dir(config)
  raw_path = output_dir / "bigquery_light_results_raw.csv"
  dedup_path = output_dir / "bigquery_light_results_dedup.csv"
  summary_path = output_dir / "retrieval_summary.json"

  if config.use_cache and dedup_path.exists():
    cached = load_cached_results(dedup_path)
    if cached:
      return {
        "status": "cached",
        "mode": "execute" if config.execute else "dry_run",
        "query_results": [],
        "total_estimated_bytes": 0,
        "total_estimated_gb": 0.0,
        "total_estimated_usd": 0.0,
        "total_records_before_dedup": len(cached),
        "total_records_after_dedup": len(cached),
        "output_csv_path": str(dedup_path),
        "output_raw_csv_path": str(raw_path),
        "errors": [],
        "warnings": ["Loaded cached deduplicated results."],
      }

  env = check_bigquery_environment(config.project_id)
  warnings: list[str] = []
  errors: list[str] = []
  if not env.get("ready"):
    for check in env.get("checks", []):
      if check.get("status") != "ok":
        errors.append(check.get("message", ""))

  query_results: list[dict[str, Any]] = []
  all_records: list[dict] = []
  remaining = config.max_results_total

  for query_plan in query_plans:
    if remaining <= 0:
      warnings.append(f"Skipped {query_plan.intent_id}: max_results_total reached")
      continue
    per_intent_limit = min(config.max_results_per_intent, remaining, query_plan.max_results)
    result = run_query_plan(
      query_plan,
      config,
      limit=per_intent_limit,
      client_factory=client_factory,
    )
    query_results.append(result)
    if result.get("error"):
      errors.append(f"{query_plan.intent_id}: {result['error']}")
    all_records.extend(result.get("records", []))
    remaining -= result.get("record_count", 0)

  total_estimated_bytes = sum(int(item.get("estimated_bytes", 0)) for item in query_results)
  deduped_records = deduplicate_patent_records(all_records)

  raw_csv = save_records_csv(all_records, raw_path)
  dedup_csv = save_records_csv(deduped_records, dedup_path)

  summary = {
    "status": "ok" if not errors else "error",
    "mode": "execute" if config.execute else "dry_run",
    "environment": env,
    "query_results": [
      {key: value for key, value in item.items() if key != "records"}
      for item in query_results
    ],
    "total_estimated_bytes": total_estimated_bytes,
    "total_estimated_gb": bytes_to_gb(total_estimated_bytes),
    "total_estimated_usd": estimate_usd_from_bytes(total_estimated_bytes),
    "total_records_before_dedup": len(all_records),
    "total_records_after_dedup": len(deduped_records),
    "output_csv_path": dedup_csv,
    "output_raw_csv_path": raw_csv,
    "errors": errors,
    "warnings": warnings,
  }
  save_retrieval_summary(summary, summary_path)

  return {
    "status": summary["status"],
    "mode": summary["mode"],
    "query_results": query_results,
    "total_estimated_bytes": total_estimated_bytes,
    "total_estimated_gb": bytes_to_gb(total_estimated_bytes),
    "total_estimated_usd": estimate_usd_from_bytes(total_estimated_bytes),
    "total_records_before_dedup": len(all_records),
    "total_records_after_dedup": len(deduped_records),
    "output_csv_path": dedup_csv,
    "output_raw_csv_path": raw_csv,
    "output_summary_path": str(summary_path),
    "errors": errors,
    "warnings": warnings,
  }
