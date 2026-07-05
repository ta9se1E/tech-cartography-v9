"""BigQuery cost preview helpers for study demo search plan Step 1."""

from __future__ import annotations

from typing import Any, Mapping

from services_v9.study_demo_config import (
  get_study_demo_bigquery_max_bytes_billed,
  get_study_demo_bigquery_price_per_tib_usd,
)

from .constants import STUDY_DEMO_BQ_MAX_BYTES_BILLED_DEFAULT


def bytes_to_gib(num_bytes: int) -> float:
  return round(int(num_bytes or 0) / (1024**3), 4)


def bytes_to_tib(num_bytes: int) -> float:
  return round(int(num_bytes or 0) / (1024**4), 6)


def reference_cost_usd(num_bytes: int, *, price_per_tib: float) -> float | None:
  estimated = int(num_bytes or 0)
  if estimated <= 0 or price_per_tib <= 0:
    return None
  return round((estimated / (1024**4)) * price_per_tib, 4)


def sanitize_dry_run_for_plan(dry_run: Mapping[str, Any]) -> dict[str, Any]:
  allowed = (
    "dry_run_status",
    "estimated_bytes",
    "estimated_gb",
    "estimated_cost_usd",
    "maximum_bytes_billed",
    "would_be_blocked_by_max_bytes",
    "query_validation",
    "execute_enabled",
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
  max_bytes = int(
    get_study_demo_bigquery_max_bytes_billed(environ)
    or enriched.get("maximum_bytes_billed")
    or STUDY_DEMO_BQ_MAX_BYTES_BILLED_DEFAULT
  )
  price_per_tib = get_study_demo_bigquery_price_per_tib_usd(environ)
  dry_status = str(dry_run.get("dry_run_status", "") or "")
  estimated_bytes = int(dry_run.get("estimated_bytes", 0) or 0)
  blocked = bool(dry_run.get("would_be_blocked_by_max_bytes", False))
  sanitized = sanitize_dry_run_for_plan(dry_run)

  enriched["dry_run"] = sanitized
  enriched["dry_run_fingerprint"] = dry_run_fingerprint
  enriched["dry_run_required"] = False
  enriched["maximum_bytes_billed"] = max_bytes
  enriched["bigquery_max_bytes_billed"] = max_bytes
  enriched["bigquery_estimated_bytes"] = estimated_bytes
  enriched["bigquery_estimated_gib"] = bytes_to_gib(estimated_bytes)
  enriched["bigquery_estimated_tib"] = bytes_to_tib(estimated_bytes)
  enriched["bigquery_reference_cost_usd"] = reference_cost_usd(estimated_bytes, price_per_tib=price_per_tib)
  enriched["estimated_bytes"] = estimated_bytes

  if dry_status != "ok":
    enriched["status"] = "dry_run_failed"
    enriched["bigquery_execution_allowed"] = False
    return enriched

  if estimated_bytes <= 0:
    enriched["status"] = "dry_run_zero_bytes"
    enriched["zero_bytes_reason"] = "BigQuery dry-run completed with total_bytes_processed=0"
    enriched["bigquery_execution_allowed"] = False
    return enriched

  if blocked or (max_bytes > 0 and estimated_bytes > max_bytes):
    enriched["status"] = "ready"
    enriched["bigquery_execution_allowed"] = False
    enriched["cost_guard_reason"] = "estimated_bytes exceeds maximum_bytes_billed"
    return enriched

  enriched["status"] = "ready"
  enriched["bigquery_execution_allowed"] = True
  return enriched


def build_bigquery_cost_estimate(
  patent_plan: Mapping[str, Any],
  *,
  environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
  max_bytes = int(
    get_study_demo_bigquery_max_bytes_billed(environ)
    or patent_plan.get("bigquery_max_bytes_billed")
    or STUDY_DEMO_BQ_MAX_BYTES_BILLED_DEFAULT
  )
  estimated_bytes = int(patent_plan.get("bigquery_estimated_bytes", patent_plan.get("estimated_bytes", 0)) or 0)
  price_per_tib = get_study_demo_bigquery_price_per_tib_usd(environ)
  return {
    "bigquery_max_bytes_billed": max_bytes,
    "bigquery_estimated_bytes": estimated_bytes,
    "bigquery_estimated_gib": patent_plan.get("bigquery_estimated_gib", bytes_to_gib(estimated_bytes)),
    "bigquery_estimated_tib": patent_plan.get("bigquery_estimated_tib", bytes_to_tib(estimated_bytes)),
    "bigquery_reference_cost_usd": patent_plan.get(
      "bigquery_reference_cost_usd",
      reference_cost_usd(estimated_bytes, price_per_tib=price_per_tib),
    ),
    "bigquery_execution_allowed": bool(patent_plan.get("bigquery_execution_allowed", False)),
  }
