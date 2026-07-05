"""BigQuery cost preview helpers for study demo search plan Step 1."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from services_v9.study_demo_config import (
  get_study_demo_bigquery_max_bytes_billed,
  get_study_demo_bigquery_price_per_tib_usd,
)

from .constants import STUDY_DEMO_BQ_MAX_BYTES_BILLED_DEFAULT

BYTES_PER_TIB = 1024**4


def bytes_to_gib(num_bytes: int) -> float:
  return round(int(num_bytes or 0) / (1024**3), 4)


def bytes_to_tib(num_bytes: int) -> float:
  return round(int(num_bytes or 0) / BYTES_PER_TIB, 6)


def reference_cost_usd(num_bytes: int, *, price_per_tib: float) -> float | None:
  estimated = int(num_bytes or 0)
  if estimated <= 0 or price_per_tib <= 0:
    return None
  return round((estimated / BYTES_PER_TIB) * price_per_tib, 4)


def resolve_bigquery_max_bytes_billed(
  *,
  environ: Mapping[str, str] | None = None,
  fallback: int | None = None,
) -> int:
  return int(
    get_study_demo_bigquery_max_bytes_billed(environ)
    or fallback
    or STUDY_DEMO_BQ_MAX_BYTES_BILLED_DEFAULT
  )


def normalize_study_demo_patent_validation_rows(
  rows: Sequence[Mapping[str, Any]],
  *,
  max_bytes: int,
) -> list[dict[str, str]]:
  filtered: list[dict[str, str]] = []
  for row in rows:
    status = str(row.get("status", "") or "")
    message = str(row.get("message", "") or "")
    if max_bytes > 0 and "maximum_bytes_billed が未設定" in message:
      continue
    filtered.append({"status": status, "message": message})
  if max_bytes <= 0:
    if any(item["status"] == "error" for item in filtered):
      return filtered
    return filtered + [{"status": "error", "message": "maximum_bytes_billed が未設定です。"}]
  if any(item["status"] == "error" for item in filtered):
    return filtered
  if any(item["status"] == "ok" for item in filtered):
    return [item for item in filtered if item["status"] == "ok"] or [{"status": "ok", "message": "validation passed"}]
  return [{"status": "ok", "message": "validation passed"}]


def evaluate_bigquery_execution_allowed(
  *,
  dry_run_status: str,
  estimated_bytes: int,
  max_bytes: int,
  validation_rows: Sequence[Mapping[str, Any]],
  would_be_blocked_by_max_bytes: bool = False,
) -> bool:
  if str(dry_run_status or "") != "ok":
    return False
  if int(estimated_bytes or 0) <= 0:
    return False
  if max_bytes <= 0:
    return False
  if would_be_blocked_by_max_bytes or int(estimated_bytes) > int(max_bytes):
    return False
  if any(str(row.get("status", "") or "") == "error" for row in validation_rows):
    return False
  return True


def build_normalized_dry_run_view(
  dry_run: Mapping[str, Any],
  *,
  max_bytes: int,
  price_per_tib: float,
  validation_rows: Sequence[Mapping[str, Any]],
  execution_allowed: bool,
) -> dict[str, Any]:
  estimated_bytes = int(dry_run.get("estimated_bytes", 0) or 0)
  cost_usd = reference_cost_usd(estimated_bytes, price_per_tib=price_per_tib)
  normalized_validation = normalize_study_demo_patent_validation_rows(validation_rows, max_bytes=max_bytes)
  view = sanitize_dry_run_for_plan(dry_run)
  view["maximum_bytes_billed"] = max_bytes
  view["estimated_bytes"] = estimated_bytes
  view["estimated_cost_usd"] = cost_usd
  view["query_validation"] = normalized_validation
  view["execution_performed"] = False
  view["execution_allowed"] = execution_allowed
  view.pop("execute_enabled", None)
  return view


def sanitize_dry_run_for_plan(dry_run: Mapping[str, Any]) -> dict[str, Any]:
  allowed = (
    "dry_run_status",
    "estimated_bytes",
    "estimated_gb",
    "estimated_cost_usd",
    "maximum_bytes_billed",
    "would_be_blocked_by_max_bytes",
    "query_validation",
    "execution_performed",
    "execution_allowed",
    "project_id",
    "location",
    "job_id",
    "total_bytes_processed",
    "total_bytes_billed",
    "cache_hit",
    "started_at",
    "finished_at",
    "sql_fingerprint",
    "selected_columns",
    "error_category",
    "error",
  )
  return {key: dry_run.get(key) for key in allowed if key in dry_run}


def enrich_patent_plan_with_dry_run(
  plan: dict[str, Any],
  dry_run: Mapping[str, Any],
  *,
  dry_run_fingerprint: str,
  environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
  enriched = dict(plan)
  max_bytes = resolve_bigquery_max_bytes_billed(
    environ=environ,
    fallback=int(enriched.get("maximum_bytes_billed", 0) or 0),
  )
  price_per_tib = get_study_demo_bigquery_price_per_tib_usd(environ)
  dry_status = str(dry_run.get("dry_run_status", "") or "")
  estimated_bytes = int(dry_run.get("estimated_bytes", 0) or 0)
  blocked = bool(dry_run.get("would_be_blocked_by_max_bytes", False))
  raw_validation = list(dry_run.get("query_validation", []) or enriched.get("validation_rows", []) or [])
  normalized_validation = normalize_study_demo_patent_validation_rows(raw_validation, max_bytes=max_bytes)
  execution_allowed = evaluate_bigquery_execution_allowed(
    dry_run_status=dry_status,
    estimated_bytes=estimated_bytes,
    max_bytes=max_bytes,
    validation_rows=normalized_validation,
    would_be_blocked_by_max_bytes=blocked,
  )
  cost_usd = reference_cost_usd(estimated_bytes, price_per_tib=price_per_tib)

  enriched["dry_run"] = build_normalized_dry_run_view(
    dry_run,
    max_bytes=max_bytes,
    price_per_tib=price_per_tib,
    validation_rows=raw_validation,
    execution_allowed=execution_allowed,
  )
  enriched["validation_rows"] = normalized_validation
  enriched["dry_run_fingerprint"] = dry_run_fingerprint
  enriched["dry_run_required"] = False
  enriched["maximum_bytes_billed"] = max_bytes
  enriched["bigquery_max_bytes_billed"] = max_bytes
  enriched["bigquery_estimated_bytes"] = estimated_bytes
  enriched["bigquery_estimated_gib"] = bytes_to_gib(estimated_bytes)
  enriched["bigquery_estimated_tib"] = bytes_to_tib(estimated_bytes)
  enriched["bigquery_reference_cost_usd"] = cost_usd
  enriched["price_per_tib_usd"] = price_per_tib
  enriched["estimated_bytes"] = estimated_bytes
  enriched["bigquery_execution_allowed"] = execution_allowed

  if dry_status != "ok":
    enriched["status"] = "dry_run_failed"
    return enriched

  if estimated_bytes <= 0:
    enriched["status"] = "dry_run_zero_bytes"
    enriched["zero_bytes_reason"] = "BigQuery dry-run completed with total_bytes_processed=0"
    return enriched

  if not execution_allowed:
    enriched["status"] = "ready"
    enriched["cost_guard_reason"] = "estimated_bytes exceeds maximum_bytes_billed"
    return enriched

  enriched["status"] = "ready"
  return enriched


def build_bigquery_cost_estimate(
  patent_plan: Mapping[str, Any],
  *,
  environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
  max_bytes = resolve_bigquery_max_bytes_billed(
    environ=environ,
    fallback=int(patent_plan.get("bigquery_max_bytes_billed", patent_plan.get("maximum_bytes_billed", 0)) or 0),
  )
  estimated_bytes = int(patent_plan.get("bigquery_estimated_bytes", patent_plan.get("estimated_bytes", 0)) or 0)
  price_per_tib = get_study_demo_bigquery_price_per_tib_usd(environ)
  cost_usd = patent_plan.get("bigquery_reference_cost_usd")
  if cost_usd is None:
    cost_usd = reference_cost_usd(estimated_bytes, price_per_tib=price_per_tib)
  return {
    "bigquery_max_bytes_billed": max_bytes,
    "bigquery_estimated_bytes": estimated_bytes,
    "bigquery_estimated_gib": patent_plan.get("bigquery_estimated_gib", bytes_to_gib(estimated_bytes)),
    "bigquery_estimated_tib": patent_plan.get("bigquery_estimated_tib", bytes_to_tib(estimated_bytes)),
    "bigquery_reference_cost_usd": cost_usd,
    "bigquery_execution_allowed": bool(patent_plan.get("bigquery_execution_allowed", False)),
    "price_per_tib_usd": price_per_tib,
  }
