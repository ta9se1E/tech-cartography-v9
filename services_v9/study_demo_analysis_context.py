"""Active Analysis Context for Study Demo downstream tabs."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from services_v9.study_demo_config import PRODUCTION_PERSIST_BUCKET, get_study_demo_bucket
from services_v9.study_demo_storage import validate_study_demo_write_target

ACTIVE_CONTEXT_SCHEMA_VERSION = 1
ACTIVE_CONTEXT_OBJECT = "analysis_context/active_context.json"
ACTIVE_CONTEXT_AUDIT_PREFIX = "analysis_context/audit/"
FORBIDDEN_CONTEXT_KEYS = frozenset(
  {
    "password",
    "api_key",
    "secret",
    "cookie",
    "authorization",
    "smtp",
    "tavily_api_key",
    "openalex_api_key",
  }
)


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).isoformat()


def _search_run_prefix(search_run_id: str) -> str:
  run_id = str(search_run_id or "").strip()
  if not run_id or not re.fullmatch(r"[A-Za-z0-9._-]+", run_id):
    raise ValueError("invalid search_run_id")
  return f"search_runs/{run_id}/"


def reject_production_bucket_path(path: str) -> None:
  bucket = get_study_demo_bucket()
  if PRODUCTION_PERSIST_BUCKET in str(path or ""):
    raise ValueError("production bucket path is forbidden")
  if "tech-cartography-v9-weekly-persist" in str(path or ""):
    raise ValueError("production persist bucket path is forbidden")


def build_active_context_from_run(
  *,
  search_run_id: str,
  artifacts: Mapping[str, Any],
  bucket_name: str | None = None,
  selected_by: str = "shared_study_demo_user",
) -> dict[str, Any]:
  bucket = str(bucket_name or get_study_demo_bucket()).strip()
  validate_study_demo_write_target(bucket)
  reject_production_bucket_path(bucket)

  summary = dict(artifacts.get("search_request.json", {}) or {})
  integrated = dict(artifacts.get("integrated_signals.json", {}) or {})
  provider_status = dict(artifacts.get("provider_status.json", {}) or {})
  relevance_summary = dict(integrated.get("relevance_summary", {}) or {})

  patent_count = int(integrated.get("patent_count", 0) or 0)
  paper_count = int(integrated.get("paper_count", 0) or 0)
  web_count = int(integrated.get("web_count", 0) or 0)
  if not any((patent_count, paper_count, web_count)):
    signals = list(integrated.get("signals", []) or [])
    patent_count = sum(1 for item in signals if str(item.get("source_type", "")) == "patent")
    paper_count = sum(1 for item in signals if str(item.get("source_type", "")) == "paper")
    web_count = sum(1 for item in signals if str(item.get("source_type", "")) == "web_company")

  prefix = _search_run_prefix(search_run_id)
  ctx = {
    "schema_version": ACTIVE_CONTEXT_SCHEMA_VERSION,
    "context_type": "temporary_search",
    "active_search_run_id": search_run_id,
    "selected_at": _utc_now_iso(),
    "selected_by": selected_by,
    "source_bucket": bucket,
    "source_prefix": prefix,
    "theme": str(summary.get("theme", "") or ""),
    "search_request_ref": f"{prefix}search_request.json",
    "provider_status_ref": f"{prefix}provider_status.json",
    "integrated_signals_ref": f"{prefix}integrated_signals.json",
    "usage_metrics_ref": f"{prefix}usage_metrics.json",
    "search_report_ref": f"{prefix}search_report.md",
    "provider_counts": {"patent": patent_count, "paper": paper_count, "web": web_count},
    "tier_counts": {
      "A": int(relevance_summary.get("tier_a", 0) or 0),
      "B": int(relevance_summary.get("tier_b", 0) or 0),
      "C": int(relevance_summary.get("tier_c", 0) or 0),
      "D": int(relevance_summary.get("tier_d", 0) or 0),
    },
    "active_data_source": "temporary_search",
    "external_execution_enabled": False,
    "email_enabled": False,
    "automatic_weekly_enabled": False,
    "ranked_count": int(integrated.get("ranked_count", len(integrated.get("signals", []) or [])) or 0),
  }
  return sanitize_active_context(ctx)


def sanitize_active_context(payload: Mapping[str, Any]) -> dict[str, Any]:
  cleaned = dict(payload)
  for key in list(cleaned.keys()):
    if any(token in str(key).lower() for token in FORBIDDEN_CONTEXT_KEYS):
      cleaned.pop(key, None)
  blob = json.dumps(cleaned, ensure_ascii=False).lower()
  if any(token in blob for token in ("api_key", "password", "secret", "cookie")):
    raise ValueError("forbidden secret-like value in active context")
  if "signals" in cleaned:
    raise ValueError("signal bodies must not be copied into active context")
  reject_production_bucket_path(str(cleaned.get("source_bucket", "")))
  reject_production_bucket_path(str(cleaned.get("source_prefix", "")))
  return cleaned


def validate_active_context(payload: Mapping[str, Any]) -> list[str]:
  errors: list[str] = []
  if int(payload.get("schema_version", 0) or 0) != ACTIVE_CONTEXT_SCHEMA_VERSION:
    errors.append("unsupported schema_version")
  if str(payload.get("context_type", "")) != "temporary_search":
    errors.append("unsupported context_type")
  if not str(payload.get("active_search_run_id", "")).strip():
    errors.append("active_search_run_id is required")
  if not str(payload.get("source_prefix", "")).startswith("search_runs/"):
    errors.append("source_prefix must reference search_runs/")
  return errors


def is_same_active_context(existing: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
  return str(existing.get("active_search_run_id", "")) == str(candidate.get("active_search_run_id", ""))


def load_active_context_from_storage(
  *,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  bucket_name = get_study_demo_bucket(environ)
  validate_study_demo_write_target(bucket_name, environ=environ)
  client = storage_client if storage_client is not None else _build_client()
  blob = client.bucket(bucket_name).blob(ACTIVE_CONTEXT_OBJECT)
  if not blob.exists():
    return {"status": "missing", "context": None, "generation": None}
  blob.reload()
  payload = json.loads(blob.download_as_bytes().decode("utf-8"))
  errors = validate_active_context(payload)
  if errors:
    return {"status": "invalid", "context": payload, "generation": blob.generation, "errors": errors}
  return {"status": "ok", "context": sanitize_active_context(payload), "generation": blob.generation}


def save_active_context_to_storage(
  candidate: Mapping[str, Any],
  *,
  expected_generation: int | None = None,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
  selected_by: str = "shared_study_demo_user",
) -> dict[str, Any]:
  bucket_name = get_study_demo_bucket(environ)
  validate_study_demo_write_target(bucket_name, environ=environ)
  ctx = sanitize_active_context({**dict(candidate), "selected_by": selected_by, "selected_at": _utc_now_iso()})
  errors = validate_active_context(ctx)
  if errors:
    return {"status": "validation_error", "errors": errors}

  client = storage_client if storage_client is not None else _build_client()
  bucket = client.bucket(bucket_name)
  blob = bucket.blob(ACTIVE_CONTEXT_OBJECT)

  existing_generation = expected_generation
  existing_context: dict[str, Any] | None = None
  if blob.exists():
    blob.reload()
    if existing_generation is None:
      existing_generation = blob.generation
    existing_raw = blob.download_as_bytes().decode("utf-8")
    if existing_raw.strip():
      existing_context = sanitize_active_context(json.loads(existing_raw))
      if is_same_active_context(existing_context, ctx):
        return {
          "status": "unchanged",
          "context": existing_context,
          "generation": blob.generation,
          "idempotent": True,
        }
  else:
    existing_generation = 0 if existing_generation is None else existing_generation

  text = json.dumps(ctx, ensure_ascii=False, indent=2) + "\n"
  try:
    if existing_generation is None:
      blob.upload_from_string(text, content_type="application/json", if_generation_match=0)
    else:
      blob.upload_from_string(text, content_type="application/json", if_generation_match=existing_generation)
  except Exception as exc:  # noqa: BLE001
    return {"status": "conflict", "message": str(exc), "requires_reload": True}

  blob.reload()
  audit_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
  audit_blob = bucket.blob(f"{ACTIVE_CONTEXT_AUDIT_PREFIX}{audit_id}.json")
  audit_blob.upload_from_string(
    json.dumps(
      {
        "audit_id": audit_id,
        "saved_at": _utc_now_iso(),
        "active_search_run_id": ctx.get("active_search_run_id"),
        "selected_by": selected_by,
        "previous_run_id": (existing_context or {}).get("active_search_run_id"),
        "generation": blob.generation,
      },
      ensure_ascii=False,
      indent=2,
    )
    + "\n",
    content_type="application/json",
  )
  return {"status": "saved", "context": ctx, "generation": blob.generation, "audit_id": audit_id}


def _build_client():
  from google.cloud import storage

  return storage.Client()
