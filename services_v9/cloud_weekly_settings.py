"""Weekly delivery settings for local/cloud v9 operation."""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from .cloud_runtime import (
  get_persist_bucket_name,
  get_persist_root,
  get_runtime_mode,
  get_weekly_config_object_name,
  is_cloud_runtime,
)
from .email_delivery import load_email_delivery_config
from .persistence import ensure_v9_run_dirs, write_json_atomic

CLOUD_WEEKLY_SETTINGS_SCHEMA_VERSION = "v9.6c"
DEFAULT_WEEKDAY = "MON"
DEFAULT_TIMEZONE = "Asia/Tokyo"
VALID_WEEKDAYS = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}
VALID_EMAIL_MODES = {"self_only", "preview"}
_WEEKDAY_TO_CRON = {
  "MON": 1,
  "TUE": 2,
  "WED": 3,
  "THU": 4,
  "FRI": 5,
  "SAT": 6,
  "SUN": 0,
}
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def default_weekly_delivery_settings() -> dict[str, Any]:
  settings = {
    "schema_version": CLOUD_WEEKLY_SETTINGS_SCHEMA_VERSION,
    "enabled": False,
    "recipient_email": "",
    "weekday": DEFAULT_WEEKDAY,
    "hour": 9,
    "minute": 0,
    "timezone": DEFAULT_TIMEZONE,
    "cron_expression": build_cron_expression(DEFAULT_WEEKDAY, 9, 0),
    "email_mode": "self_only",
    "updated_at": "",
    "updated_by": "streamlit",
    "revision": 0,
    "scheduler_applied_revision": 0,
    "last_scheduler_apply_status": "",
    "last_scheduler_apply_at": "",
    "last_scheduler_known_state": "",
  }
  return settings


def build_cron_expression(weekday: str, hour: int, minute: int) -> str:
  weekday_key = str(weekday or "").strip().upper()
  if weekday_key not in _WEEKDAY_TO_CRON:
    raise ValueError("weekday が不正です。")
  if not 0 <= int(hour) <= 23:
    raise ValueError("hour は 0-23 の範囲である必要があります。")
  if not 0 <= int(minute) <= 59:
    raise ValueError("minute は 0-59 の範囲である必要があります。")
  return f"{int(minute)} {int(hour)} * * {_WEEKDAY_TO_CRON[weekday_key]}"


def mask_email_address(value: str) -> str:
  text = str(value or "").strip()
  if "@" not in text:
    return ""
  local_part, domain = text.split("@", 1)
  if not local_part:
    return f"***@{domain}"
  if len(local_part) == 1:
    masked_local = local_part + "***"
  elif len(local_part) == 2:
    masked_local = local_part[0] + "*" + local_part[1]
  else:
    masked_local = local_part[0] + ("*" * max(len(local_part) - 2, 1)) + local_part[-1]
  return f"{masked_local}@{domain}"


def resolve_allowed_recipients(environ: Mapping[str, str] | None = None) -> tuple[str, ...]:
  env = environ if environ is not None else os.environ
  direct_value = str(env.get("V9_ALLOWED_RECIPIENTS", "") or "").strip()
  if direct_value:
    return tuple(sorted({item.lower() for item in _split_emails(direct_value) if item}))
  config = load_email_delivery_config(env)
  allowlist = tuple(sorted({item.lower() for item in config.recipient_allowlist if item}))
  if allowlist:
    return allowlist
  fallback = [config.self_recipient, config.sender]
  return tuple(sorted({item.strip().lower() for item in fallback if _is_valid_single_email(item)}))


def resolve_weekly_delivery_settings_path(
  *,
  base_dir: Path | str | None = None,
  environ: Mapping[str, str] | None = None,
) -> Path:
  env = environ if environ is not None else os.environ
  root = Path(base_dir) if base_dir is not None else get_persist_root(env)
  object_name = get_weekly_config_object_name(env)
  requested = Path(object_name)
  if requested.is_absolute():
    return requested.resolve()
  return (root / requested).resolve()


def load_weekly_delivery_settings(
  *,
  base_dir: Path | str | None = None,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  document = _read_settings_document(base_dir=base_dir, environ=environ, storage_client=storage_client)
  raw_settings = dict(document.get("payload", {}) or {})
  merged = _merge_settings(default_weekly_delivery_settings(), raw_settings)
  validation = validate_weekly_delivery_settings(merged, environ=environ)
  normalized = dict(validation.get("normalized_settings", {}) or default_weekly_delivery_settings())
  if not normalized.get("updated_at") and raw_settings.get("updated_at"):
    normalized["updated_at"] = str(raw_settings.get("updated_at", "") or "")
  return normalized


def validate_weekly_delivery_settings(
  settings: Mapping[str, Any] | None,
  *,
  environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
  merged = _merge_settings(default_weekly_delivery_settings(), dict(settings or {}))
  errors: list[str] = []
  warnings: list[str] = []

  merged["schema_version"] = CLOUD_WEEKLY_SETTINGS_SCHEMA_VERSION
  merged["enabled"] = bool(merged.get("enabled", False))
  merged["recipient_email"] = str(merged.get("recipient_email", "") or "").strip().lower()
  merged["weekday"] = str(merged.get("weekday", DEFAULT_WEEKDAY) or DEFAULT_WEEKDAY).strip().upper()
  merged["hour"] = _safe_int(merged.get("hour", 9), 9)
  merged["minute"] = _safe_int(merged.get("minute", 0), 0)
  merged["timezone"] = str(merged.get("timezone", DEFAULT_TIMEZONE) or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
  merged["email_mode"] = str(merged.get("email_mode", "self_only") or "self_only").strip().lower()
  merged["updated_at"] = str(merged.get("updated_at", "") or "").strip()
  merged["updated_by"] = str(merged.get("updated_by", "streamlit") or "streamlit").strip() or "streamlit"
  merged["revision"] = max(_safe_int(merged.get("revision", 0), 0), 0)
  merged["scheduler_applied_revision"] = max(_safe_int(merged.get("scheduler_applied_revision", 0), 0), 0)
  merged["last_scheduler_apply_status"] = str(merged.get("last_scheduler_apply_status", "") or "").strip()
  merged["last_scheduler_apply_at"] = str(merged.get("last_scheduler_apply_at", "") or "").strip()
  merged["last_scheduler_known_state"] = str(merged.get("last_scheduler_known_state", "") or "").strip()

  if merged["weekday"] not in VALID_WEEKDAYS:
    errors.append("weekday が不正です。")
  if not 0 <= merged["hour"] <= 23:
    errors.append("hour は 0-23 の範囲である必要があります。")
  if not 0 <= merged["minute"] <= 59:
    errors.append("minute は 0-59 の範囲である必要があります。")
  try:
    ZoneInfo(merged["timezone"])
  except Exception:  # noqa: BLE001
    errors.append("timezone は IANA timezone である必要があります。")

  if merged["email_mode"] not in VALID_EMAIL_MODES:
    errors.append("email_mode は `self_only` または `preview` である必要があります。")

  if merged["recipient_email"]:
    if not _is_valid_single_email(merged["recipient_email"]):
      errors.append("recipient_email が不正です。")
  elif merged["enabled"]:
    errors.append("enabled=true の場合は recipient_email が必要です。")

  allowed_recipients = resolve_allowed_recipients(environ)
  if merged["recipient_email"] and allowed_recipients and merged["recipient_email"] not in set(allowed_recipients):
    errors.append("recipient_email が許可された allowlist に含まれていません。")
  if not allowed_recipients:
    warnings.append("有効な recipient allowlist が未設定です。")

  try:
    merged["cron_expression"] = build_cron_expression(merged["weekday"], merged["hour"], merged["minute"])
  except ValueError as exc:
    errors.append(str(exc))
    merged["cron_expression"] = ""

  return {
    "status": "ok" if not errors else "blocked",
    "errors": errors,
    "warnings": warnings,
    "normalized_settings": merged,
    "allowed_recipients": allowed_recipients,
  }


def save_weekly_delivery_settings(
  settings: Mapping[str, Any] | None,
  *,
  updated_by: str = "streamlit",
  increment_revision: bool = True,
  base_dir: Path | str | None = None,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  env = environ if environ is not None else os.environ
  from services_v9.study_demo_config import is_study_demo_mode
  from services_v9.study_demo_guard import assert_write_allowed

  if is_study_demo_mode(env):
    assert_write_allowed("weekly_delivery_settings", environ=env)
  document = _read_settings_document(base_dir=base_dir, environ=env, storage_client=storage_client)
  current_settings = dict(document.get("payload", {}) or {})
  merged = _merge_settings(current_settings or default_weekly_delivery_settings(), dict(settings or {}))
  validation = validate_weekly_delivery_settings(merged, environ=env)
  errors = list(validation.get("errors", []) or [])
  if errors:
    raise RuntimeError("週次自動配信設定を保存できません: " + " / ".join(errors))
  normalized = dict(validation.get("normalized_settings", {}) or {})
  normalized["updated_by"] = str(updated_by or "streamlit").strip() or "streamlit"
  normalized["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
  current_revision = max(_safe_int(current_settings.get("revision", 0), 0), 0)
  normalized["revision"] = current_revision + 1 if increment_revision else max(_safe_int(normalized.get("revision", current_revision), current_revision), current_revision)
  normalized["cron_expression"] = build_cron_expression(
    normalized["weekday"],
    normalized["hour"],
    normalized["minute"],
  )

  secret_tokens = {"smtp_password", "tavily_api_key", "credential", "token"}
  for key in list(normalized):
    lowered = key.lower()
    if any(token in lowered for token in secret_tokens):
      normalized.pop(key, None)

  if is_cloud_runtime(env) and get_persist_bucket_name(env):
    bucket_name = get_persist_bucket_name(env)
    object_name = get_weekly_config_object_name(env)
    _write_settings_to_gcs(
      bucket_name=bucket_name,
      object_name=object_name,
      payload=normalized,
      storage_client=storage_client,
      if_generation_match=document.get("generation"),
    )
    return {
      "settings": normalized,
      "storage_mode": "cloud",
      "location": f"gs://{bucket_name}/{object_name}",
    }

  path = resolve_weekly_delivery_settings_path(base_dir=base_dir, environ=env)
  ensure_v9_run_dirs(path.parent.parent if path.parent.name == "v9_config" else (base_dir if base_dir is not None else None))
  write_json_atomic(path, normalized)
  return {
    "settings": normalized,
    "storage_mode": "local",
    "location": str(path),
  }


def _read_settings_document(
  *,
  base_dir: Path | str | None,
  environ: Mapping[str, str] | None,
  storage_client: Any | None,
) -> dict[str, Any]:
  env = environ if environ is not None else os.environ
  if is_cloud_runtime(env) and get_persist_bucket_name(env):
    bucket_name = get_persist_bucket_name(env)
    object_name = get_weekly_config_object_name(env)
    return _read_settings_from_gcs(bucket_name=bucket_name, object_name=object_name, storage_client=storage_client)
  path = resolve_weekly_delivery_settings_path(base_dir=base_dir, environ=env)
  if not path.exists():
    return {"payload": default_weekly_delivery_settings(), "generation": None, "location": str(path)}
  try:
    payload = json.loads(path.read_text(encoding="utf-8"))
  except json.JSONDecodeError:
    return {"payload": default_weekly_delivery_settings(), "generation": None, "location": str(path), "warning": "broken_json"}
  return {"payload": dict(payload or {}), "generation": None, "location": str(path)}


def _read_settings_from_gcs(
  *,
  bucket_name: str,
  object_name: str,
  storage_client: Any | None,
) -> dict[str, Any]:
  client = storage_client if storage_client is not None else _build_storage_client()
  bucket = client.bucket(bucket_name)
  blob = bucket.blob(object_name)
  if not blob.exists():
    return {"payload": default_weekly_delivery_settings(), "generation": None, "location": f"gs://{bucket_name}/{object_name}"}
  raw_text = blob.download_as_text(encoding="utf-8")
  try:
    payload = json.loads(raw_text)
  except json.JSONDecodeError:
    payload = default_weekly_delivery_settings()
  return {
    "payload": dict(payload or {}),
    "generation": getattr(blob, "generation", None),
    "location": f"gs://{bucket_name}/{object_name}",
  }


def _write_settings_to_gcs(
  *,
  bucket_name: str,
  object_name: str,
  payload: dict[str, Any],
  storage_client: Any | None,
  if_generation_match: Any | None,
) -> None:
  client = storage_client if storage_client is not None else _build_storage_client()
  bucket = client.bucket(bucket_name)
  blob = bucket.blob(object_name)
  upload_kwargs: dict[str, Any] = {}
  if if_generation_match is None:
    upload_kwargs["if_generation_match"] = 0
  else:
    upload_kwargs["if_generation_match"] = int(if_generation_match)
  try:
    blob.upload_from_string(
      json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
      content_type="application/json; charset=utf-8",
      **upload_kwargs,
    )
  except Exception:
    if "if_generation_match" in upload_kwargs and upload_kwargs["if_generation_match"] == 0:
      blob.upload_from_string(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        content_type="application/json; charset=utf-8",
      )
      return
    raise


def _build_storage_client():
  from google.cloud import storage

  return storage.Client()


def _split_emails(value: str) -> list[str]:
  return [
    item.strip().lower()
    for item in re.split(r"[,;\n]+", str(value or ""))
    if item.strip()
  ]


def _is_valid_single_email(value: str) -> bool:
  text = str(value or "").strip()
  return bool(text) and "," not in text and bool(_EMAIL_PATTERN.match(text))


def _merge_settings(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
  merged = deepcopy(dict(base or {}))
  for key, value in dict(override or {}).items():
    merged[key] = deepcopy(value)
  return merged


def _safe_int(value: Any, default: int) -> int:
  try:
    return int(value)
  except (TypeError, ValueError):
    return default


__all__ = [
  "CLOUD_WEEKLY_SETTINGS_SCHEMA_VERSION",
  "VALID_EMAIL_MODES",
  "VALID_WEEKDAYS",
  "build_cron_expression",
  "default_weekly_delivery_settings",
  "load_weekly_delivery_settings",
  "mask_email_address",
  "resolve_allowed_recipients",
  "resolve_weekly_delivery_settings_path",
  "save_weekly_delivery_settings",
  "validate_weekly_delivery_settings",
]
