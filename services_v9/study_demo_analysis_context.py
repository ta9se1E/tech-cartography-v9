"""Active Analysis Context for Study Demo downstream tabs."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from services_v9.study_demo_config import PRODUCTION_PERSIST_BUCKET, get_study_demo_bucket
from services_v9.study_demo_storage import validate_study_demo_read_target, validate_study_demo_write_target

ACTIVE_CONTEXT_SCHEMA_VERSION = 1
ACTIVE_CONTEXT_OBJECT = "analysis_context/active_context.json"
ACTIVE_CONTEXT_AUDIT_PREFIX = "analysis_context/audit/"
ALLOWED_CONTEXT_TYPES = frozenset(
  {
    "temporary_search",
    "watch_profile",
    "uploaded_csv",
    "uploaded_json",
    "stored_artifact",
    "legacy_demo",
  }
)
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
  validate_study_demo_read_target(bucket)
  reject_production_bucket_path(bucket)

  summary = dict(artifacts.get("search_request.json", {}) or {})
  from services_v9.study_demo_resolved_context import resolve_active_run_counts
  from services_v9.study_demo_theme_lineage import infer_run_origin

  run_origin = infer_run_origin(summary)
  context_type = "watch_profile" if run_origin == "watch_profile" else "temporary_search"
  loaded_bundle = {"search_run_id": search_run_id, "artifacts": artifacts}
  resolved = resolve_active_run_counts(
    {"active_search_run_id": search_run_id, "theme": summary.get("theme", ""), "tier_counts": {}, "provider_counts": {}},
    loaded_bundle=loaded_bundle,
  )
  integrated_source_counts = dict(resolved.get("integrated_source_counts", {}) or {})
  tier_counts = dict(resolved.get("tier_counts", {}) or {})

  prefix = _search_run_prefix(search_run_id)
  ctx = {
    "schema_version": ACTIVE_CONTEXT_SCHEMA_VERSION,
    "context_type": context_type,
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
    "provider_counts": {
      "patent": int(integrated_source_counts.get("patent", 0) or 0),
      "paper": int(integrated_source_counts.get("paper", 0) or 0),
      "web": int(integrated_source_counts.get("web", 0) or 0),
    },
    "tier_counts": {
      "A": int(tier_counts.get("A", 0) or 0),
      "B": int(tier_counts.get("B", 0) or 0),
      "C": int(tier_counts.get("C", 0) or 0),
      "D": int(tier_counts.get("D", 0) or 0),
    },
    "active_data_source": context_type,
    "external_execution_enabled": False,
    "email_enabled": False,
    "automatic_weekly_enabled": False,
    "ranked_count": int(resolved.get("integrated_ranked_count", 0) or 0),
  }
  from services_v9.study_demo_theme_lineage import enrich_active_context_with_lineage

  ctx = enrich_active_context_with_lineage(ctx, search_request=summary)
  return sanitize_active_context(ctx)


def normalize_active_context_types(payload: Mapping[str, Any]) -> dict[str, Any]:
  cleaned = dict(payload)
  run_origin = str(cleaned.get("run_origin", "") or "").strip()
  context_type = str(cleaned.get("context_type", "") or "").strip()
  if run_origin == "watch_profile":
    cleaned["context_type"] = "watch_profile"
    cleaned["active_data_source"] = "watch_profile"
  elif run_origin == "temporary_search" and not context_type:
    cleaned["context_type"] = "temporary_search"
    cleaned["active_data_source"] = str(cleaned.get("active_data_source", "") or "temporary_search")
  elif context_type in ALLOWED_CONTEXT_TYPES:
    cleaned["context_type"] = context_type
  return cleaned


def detect_context_lineage_inconsistency(payload: Mapping[str, Any]) -> list[str]:
  errors: list[str] = []
  run_origin = str(payload.get("run_origin", "") or "")
  context_type = str(payload.get("context_type", "") or "")
  if run_origin == "watch_profile" and context_type == "temporary_search":
    errors.append("context_type_run_origin_mismatch")
  return errors


def sanitize_active_context(payload: Mapping[str, Any]) -> dict[str, Any]:
  cleaned = normalize_active_context_types(dict(payload))
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
  context_type = str(payload.get("context_type", "") or "")
  if context_type not in ALLOWED_CONTEXT_TYPES:
    errors.append("unsupported context_type")
  errors.extend(detect_context_lineage_inconsistency(payload))
  if not str(payload.get("active_search_run_id", "")).strip():
    errors.append("active_search_run_id is required")
  if not str(payload.get("source_prefix", "")).startswith("search_runs/"):
    errors.append("source_prefix must reference search_runs/")
  return errors


def is_same_active_context(existing: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
  return str(existing.get("active_search_run_id", "")) == str(candidate.get("active_search_run_id", ""))


def cache_metadata_matches(existing: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
  return (
    dict(existing.get("provider_counts", {}) or {}) == dict(candidate.get("provider_counts", {}) or {})
    and dict(existing.get("tier_counts", {}) or {}) == dict(candidate.get("tier_counts", {}) or {})
    and int(existing.get("ranked_count", 0) or 0) == int(candidate.get("ranked_count", 0) or 0)
  )


def lineage_metadata_matches(existing: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
  keys = (
    "context_type",
    "active_data_source",
    "run_origin",
    "lineage_status",
    "source_theme_id",
    "source_watch_profile_id",
    "source_search_plan_id",
    "active_context_generation",
  )
  return all(existing.get(key) == candidate.get(key) for key in keys)


def load_active_context_from_storage(
  *,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  bucket_name = get_study_demo_bucket(environ)
  validate_study_demo_read_target(bucket_name, environ=environ)
  client = storage_client if storage_client is not None else _build_client()
  blob = client.bucket(bucket_name).blob(ACTIVE_CONTEXT_OBJECT)
  if not blob.exists():
    return {"status": "missing", "context": None, "generation": None}
  blob.reload()
  payload = json.loads(blob.download_as_bytes().decode("utf-8"))
  normalized = sanitize_active_context(normalize_active_context_types(payload))
  errors = validate_active_context(normalized)
  if errors:
    return {"status": "invalid", "context": normalized, "generation": blob.generation, "errors": errors}
  return {"status": "ok", "context": normalized, "generation": blob.generation}


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
      if (
        is_same_active_context(existing_context, ctx)
        and cache_metadata_matches(existing_context, ctx)
        and lineage_metadata_matches(existing_context, ctx)
      ):
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
