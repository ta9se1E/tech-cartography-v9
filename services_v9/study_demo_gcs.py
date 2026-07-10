"""GCS copy/reset helpers for the isolated v9 study demo bucket."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Iterable, Protocol

from .study_demo_config import (
  PRODUCTION_PERSIST_BUCKET,
  SEED_PREFIX,
  SOURCE_RUN_ID_DEFAULT,
  STUDY_DEMO_BUCKET_DEFAULT,
)
from .study_demo_storage import (
  ACTIVE_PREFIX,
  SEED_COPY_ALLOWLIST,
  SEED_MANIFEST_NAME,
  SEED_ROOT_ALLOWLIST,
  SENSITIVE_JSON_KEYS,
  DEMO_METADATA_LABELS,
  build_seed_manifest,
  dumps_json,
  production_weekly_run_prefix,
  reject_production_bucket,
  sanitize_watch_profile,
  sanitize_weekly_delivery_settings,
  sanitize_weekly_run_status,
  seed_object_path,
  validate_study_demo_read_target,
  validate_study_demo_write_target,
)

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SECRET_NAME_PATTERN = re.compile(
  r"tech-cartography-(?:smtp-password|tavily-api-key)"
)


class StorageClientProtocol(Protocol):
  def bucket(self, bucket_name: str) -> Any: ...


class StorageBlobProtocol(Protocol):
  def download_as_bytes(self) -> bytes: ...

  def upload_from_string(self, data: str | bytes, *, content_type: str | None = None) -> None: ...

  def reload(self) -> None: ...


def _sanitize_json_payload(relative_name: str, payload: dict[str, Any]) -> dict[str, Any]:
  if relative_name.endswith("weekly_run_status.json"):
    return sanitize_weekly_run_status(payload)
  if relative_name.endswith("watch_profile_current.json"):
    return sanitize_watch_profile(payload)
  if relative_name.endswith("weekly_delivery_config.json"):
    return sanitize_weekly_delivery_settings(payload)
  cleaned: dict[str, Any] = {}
  for key, value in payload.items():
    if str(key).lower() in SENSITIVE_JSON_KEYS:
      continue
    cleaned[key] = value
  return cleaned


def _transform_object_bytes(relative_name: str, raw: bytes) -> bytes:
  if relative_name.endswith(".json"):
    payload = json.loads(raw.decode("utf-8"))
    if isinstance(payload, dict):
      return dumps_json(_sanitize_json_payload(relative_name, payload)).encode("utf-8")
    if isinstance(payload, list):
      from .study_demo_storage import _strip_sensitive_values as strip_sensitive_values

      return dumps_json(strip_sensitive_values(payload)).encode("utf-8")
    raise ValueError(f"expected JSON object or array for {relative_name}")
  return raw


def validate_sanitized_text(text: str, *, object_name: str = "") -> list[str]:
  issues: list[str] = []
  lowered = text.lower()
  if EMAIL_PATTERN.search(text):
    issues.append("email_address_pattern")
  for token in ("smtp_password", "tavily_api_key", "secretmanager"):
    if token in lowered:
      issues.append(f"forbidden_token:{token}")
  if SECRET_NAME_PATTERN.search(text):
    issues.append("production_secret_reference")
  if "email_delivery_runs" in lowered:
    issues.append("delivery_log_reference")
  try:
    payload = json.loads(text)
  except json.JSONDecodeError:
    return issues
  if isinstance(payload, dict):
    for key, value in payload.items():
      key_lower = str(key).lower()
      if object_name.endswith("weekly_delivery_config.json"):
        if key_lower in {"recipient", "recipient_email"} and value in ("", None):
          continue
        if key_lower == "recipient_masked" and str(value or "") == "study-demo-masked":
          continue
      if key_lower in SENSITIVE_JSON_KEYS or key_lower == "recipient" or "smtp" in key_lower:
        issues.append(f"sensitive_key:{key_lower}")
    if object_name.endswith("weekly_delivery_config.json"):
      if payload.get("enabled") is not False:
        issues.append("weekly_delivery_not_disabled")
      if payload.get("email_mode") != "preview":
        issues.append("email_mode_not_preview")
    if object_name.endswith(SEED_MANIFEST_NAME):
      labels = payload.get("labels")
      if isinstance(labels, dict):
        if labels.get("source_type") != "production_copy":
          issues.append("missing_source_type")
        if labels.get("copied_for") != "study_demo":
          issues.append("missing_copied_for")
        if labels.get("external_retrieval_enabled") is not False:
          issues.append("external_retrieval_not_false")
  return issues


def validate_seed_objects(client: StorageClientProtocol, *, demo_bucket: str) -> dict[str, Any]:
  validate_study_demo_read_target(demo_bucket)
  bucket = client.bucket(demo_bucket)
  checked: list[str] = []
  issues: list[dict[str, str]] = []
  for blob in bucket.list_blobs(prefix=SEED_PREFIX):
    name = str(getattr(blob, "name", "") or "")
    if not name or name.endswith("/"):
      continue
    checked.append(name)
    text = blob.download_as_bytes().decode("utf-8", errors="replace")
    for issue in validate_sanitized_text(text, object_name=name):
      issues.append({"object": name, "issue": issue})
  return {
    "status": "ok" if not issues else "failed",
    "checked_objects": len(checked),
    "issues": issues,
  }


def copy_seed_from_production(
  client: StorageClientProtocol,
  *,
  source_run_id: str = SOURCE_RUN_ID_DEFAULT,
  demo_bucket: str = STUDY_DEMO_BUCKET_DEFAULT,
) -> dict[str, Any]:
  reject_production_bucket(demo_bucket)
  validate_study_demo_write_target(demo_bucket)
  source_bucket_name = PRODUCTION_PERSIST_BUCKET
  run_prefix = production_weekly_run_prefix(source_run_id)
  source_bucket = client.bucket(source_bucket_name)
  dest_bucket = client.bucket(demo_bucket)

  copied_objects: list[str] = []
  for name in SEED_COPY_ALLOWLIST:
    source_name = f"{run_prefix}{name}"
    dest_name = seed_object_path(f"{run_prefix}{name}")
    source_blob = source_bucket.blob(source_name)
    if not source_blob.exists():
      raise FileNotFoundError(f"missing production source object: {source_name}")
    transformed = _transform_object_bytes(name, source_blob.download_as_bytes())
    dest_blob = dest_bucket.blob(dest_name)
    content_type = "application/json" if name.endswith(".json") else "text/markdown"
    dest_blob.upload_from_string(transformed, content_type=content_type)
    copied_objects.append(dest_name)

  for name in SEED_ROOT_ALLOWLIST:
    source_name = name
    dest_name = seed_object_path(name)
    source_blob = source_bucket.blob(source_name)
    if not source_blob.exists():
      raise FileNotFoundError(f"missing production source object: {source_name}")
    transformed = _transform_object_bytes(name, source_blob.download_as_bytes())
    dest_blob = dest_bucket.blob(dest_name)
    dest_blob.upload_from_string(transformed, content_type="application/json")
    copied_objects.append(dest_name)

  config_source = "v9_config/weekly_delivery_config.json"
  config_dest = seed_object_path(config_source)
  config_blob = source_bucket.blob(config_source)
  if not config_blob.exists():
    raise FileNotFoundError(f"missing production source object: {config_source}")
  transformed = _transform_object_bytes(
    "weekly_delivery_config.json",
    config_blob.download_as_bytes(),
  )
  dest_bucket.blob(config_dest).upload_from_string(transformed, content_type="application/json")
  copied_objects.append(config_dest)

  excluded = [
    seed_object_path(f"{run_prefix}{name}") for name in ("email_preview.json", "weekly_run_config_snapshot.json")
  ]
  manifest = build_seed_manifest(
    source_run_id=source_run_id,
    copied_objects=sorted(copied_objects),
    excluded_objects=excluded,
  )
  manifest_path = seed_object_path(SEED_MANIFEST_NAME)
  dest_bucket.blob(manifest_path).upload_from_string(dumps_json(manifest), content_type="application/json")
  copied_objects.append(manifest_path)

  validation = validate_seed_objects(client, demo_bucket=demo_bucket)
  if validation["status"] != "ok":
    return {
      "status": "failed_sanitize_validation",
      "demo_bucket": demo_bucket,
      "source_run_id": source_run_id,
      "copied_object_count": len(copied_objects),
      "validation": validation,
    }
  return {
    "status": "copied",
    "demo_bucket": demo_bucket,
    "source_bucket": source_bucket_name,
    "source_run_id": source_run_id,
    "copied_object_count": len(copied_objects),
    "copied_objects": sorted(copied_objects),
    "validation": validation,
    "labels": DEMO_METADATA_LABELS,
  }


def reset_active_from_seed(
  client: StorageClientProtocol,
  *,
  demo_bucket: str = STUDY_DEMO_BUCKET_DEFAULT,
) -> dict[str, Any]:
  validate_study_demo_write_target(demo_bucket)
  bucket = client.bucket(demo_bucket)
  seed_objects = [
    str(getattr(blob, "name", "") or "")
    for blob in bucket.list_blobs(prefix=SEED_PREFIX)
    if str(getattr(blob, "name", "") or "") and not str(getattr(blob, "name", "")).endswith("/")
  ]
  if not seed_objects:
    raise FileNotFoundError("seed prefix is empty; run seed copy first")

  copied: list[str] = []
  for seed_name in sorted(seed_objects):
    if seed_name == seed_object_path(SEED_MANIFEST_NAME):
      continue
    relative = seed_name[len(SEED_PREFIX) :]
    active_name = f"{ACTIVE_PREFIX}{relative}"
    source_blob = bucket.blob(seed_name)
    dest_blob = bucket.blob(active_name)
    bucket.copy_blob(source_blob, bucket, active_name)
    copied.append(active_name)

  history_name = (
    f"reset_history/reset_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
  )
  history_payload = {
    "schema_version": "v9.7b",
    "reset_at": datetime.now(timezone.utc).isoformat(),
    "source_prefix": SEED_PREFIX,
    "target_prefix": ACTIVE_PREFIX,
    "copied_object_count": len(copied),
    "copied_objects": copied,
    "seed_unchanged": True,
  }
  bucket.blob(history_name).upload_from_string(dumps_json(history_payload), content_type="application/json")

  return {
    "status": "reset",
    "demo_bucket": demo_bucket,
    "active_object_count": len(copied),
    "history_object": history_name,
    "seed_object_count": len(seed_objects),
  }


def default_storage_client() -> StorageClientProtocol:
  from google.cloud import storage

  return storage.Client()


def count_prefix_objects(client: StorageClientProtocol, *, demo_bucket: str, prefix: str) -> int:
  bucket = client.bucket(demo_bucket)
  return sum(
    1
    for blob in bucket.list_blobs(prefix=prefix)
    if str(getattr(blob, "name", "") or "") and not str(getattr(blob, "name", "")).endswith("/")
  )


__all__ = [
  "copy_seed_from_production",
  "count_prefix_objects",
  "default_storage_client",
  "reset_active_from_seed",
  "validate_seed_objects",
  "validate_sanitized_text",
]
