"""Study demo GCS layout and sanitization helpers."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from .study_demo_config import (
  ACTIVE_PREFIX,
  PRODUCTION_PERSIST_BUCKET,
  RESET_HISTORY_PREFIX,
  SEED_PREFIX,
  SOURCE_RUN_ID_DEFAULT,
  assert_study_demo_bucket_allowed,
  get_study_demo_bucket,
  is_study_demo_mode,
)

SEED_MANIFEST_NAME = "seed_manifest.json"
DEMO_METADATA_LABELS = {
  "source_type": "production_copy",
  "copied_for": "study_demo",
  "external_retrieval_enabled": False,
}

SEED_COPY_ALLOWLIST = (
  "weekly_digest.md",
  "weekly_diff.json",
  "weekly_run_status.json",
  "retrieval_run_manifest.json",
  "provider_log.json",
  "integrated_signals.json",
  "stage_log.json",
)

SEED_ROOT_ALLOWLIST = (
  "watch_profile_current.json",
)

EXCLUDED_COPY_NAMES = (
  "email_preview.json",
  "email_delivery_log.json",
  "weekly_run_config_snapshot.json",
)

SENSITIVE_JSON_KEYS = frozenset(
  {
    "recipient",
    "recipient_masked",
    "sender",
    "sender_masked",
    "smtp_host",
    "smtp_port",
    "smtp_username",
    "from_email",
    "to_email",
    "email_address",
    "allowed_recipients",
    "delivery_log_path",
    "password",
    "secret",
    "api_key",
    "tavily_api_key",
    "smtp_password",
  }
)


def production_weekly_run_prefix(run_id: str = SOURCE_RUN_ID_DEFAULT) -> str:
  return f"weekly_runs/{run_id}/"


def seed_object_path(relative_path: str) -> str:
  normalized = str(relative_path or "").lstrip("/")
  return f"{SEED_PREFIX}{normalized}"


def active_object_path(relative_path: str) -> str:
  normalized = str(relative_path or "").lstrip("/")
  return f"{ACTIVE_PREFIX}{normalized}"


def reset_history_object_path(relative_path: str) -> str:
  normalized = str(relative_path or "").lstrip("/")
  return f"{RESET_HISTORY_PREFIX}{normalized}"


def reject_production_bucket(bucket_name: str) -> None:
  if str(bucket_name or "").strip() == PRODUCTION_PERSIST_BUCKET:
    raise ValueError("production persist bucket access is forbidden")


def validate_study_demo_write_target(bucket_name: str, *, environ: Mapping[str, str] | None = None) -> None:
  if is_study_demo_mode(environ):
    assert_study_demo_bucket_allowed(bucket_name, environ=environ)
  reject_production_bucket(bucket_name)


def _strip_sensitive_values(value: Any) -> Any:
  if isinstance(value, dict):
    cleaned: dict[str, Any] = {}
    for key, item in value.items():
      lowered = str(key).lower()
      if lowered in SENSITIVE_JSON_KEYS or "recipient" in lowered or "smtp" in lowered:
        continue
      if lowered in {"email_preview", "email_delivery"}:
        continue
      cleaned[key] = _strip_sensitive_values(item)
    return cleaned
  if isinstance(value, list):
    return [_strip_sensitive_values(item) for item in value]
  return value


def sanitize_weekly_run_status(payload: Mapping[str, Any]) -> dict[str, Any]:
  cleaned = _strip_sensitive_values(dict(payload))
  cleaned.pop("email_preview", None)
  cleaned.pop("email_preview_path", None)
  cleaned.pop("email_delivery", None)
  return cleaned


def sanitize_watch_profile(payload: Mapping[str, Any]) -> dict[str, Any]:
  cleaned = _strip_sensitive_values(dict(payload))
  return cleaned


def sanitize_weekly_delivery_settings(payload: Mapping[str, Any]) -> dict[str, Any]:
  cleaned = copy.deepcopy(dict(payload))
  cleaned["enabled"] = False
  cleaned["email_mode"] = "preview"
  cleaned["recipient"] = ""
  cleaned["recipient_masked"] = "study-demo-masked"
  cleaned.pop("scheduler", None)
  cleaned.pop("scheduler_job_name", None)
  return cleaned


def build_seed_manifest(
  *,
  source_run_id: str,
  copied_objects: list[str],
  excluded_objects: list[str],
) -> dict[str, Any]:
  return {
    "schema_version": "v9.7a",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "source_run_id": source_run_id,
    "source_bucket": PRODUCTION_PERSIST_BUCKET,
    "labels": DEMO_METADATA_LABELS,
    "copied_objects": sorted(copied_objects),
    "excluded_objects": sorted(excluded_objects),
    "notes": "実データコピー・勉強会用。外部検索とメール送信は無効。",
  }


def dumps_json(payload: Mapping[str, Any]) -> str:
  return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


__all__ = [
  "ACTIVE_PREFIX",
  "DEMO_METADATA_LABELS",
  "EXCLUDED_COPY_NAMES",
  "SEED_COPY_ALLOWLIST",
  "SEED_MANIFEST_NAME",
  "SEED_ROOT_ALLOWLIST",
  "active_object_path",
  "build_seed_manifest",
  "dumps_json",
  "production_weekly_run_prefix",
  "reject_production_bucket",
  "reset_history_object_path",
  "sanitize_watch_profile",
  "sanitize_weekly_delivery_settings",
  "sanitize_weekly_run_status",
  "seed_object_path",
  "validate_study_demo_write_target",
]
