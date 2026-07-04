"""Cloud Storage backed weekly lock helpers for v9."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from .cloud_runtime import get_persist_bucket_name

LOCK_SCHEMA_VERSION = "v9.6c"
_LOCK_SIGNATURE_PATTERN = set("0123456789abcdef")


def acquire_cloud_weekly_lock(
  watch_profile_signature: str,
  run_id: str,
  *,
  bucket_name: str = "",
  object_prefix: str = "weekly_locks",
  storage_client: Any | None = None,
  stale_timeout_seconds: int = 21600,
  now: datetime | None = None,
) -> dict[str, Any]:
  signature = str(watch_profile_signature or "").strip().lower()
  if len(signature) != 64 or any(char not in _LOCK_SIGNATURE_PATTERN for char in signature):
    return {"acquired": False, "status": "blocked", "message": "watch_profile_signature が不正です。", "lock_name": "", "payload": {}}
  if stale_timeout_seconds <= 0:
    return {"acquired": False, "status": "blocked", "message": "stale_timeout_seconds が不正です。", "lock_name": "", "payload": {}}
  if not bucket_name:
    bucket_name = get_persist_bucket_name()
  if not bucket_name:
    return {"acquired": False, "status": "blocked", "message": "V9_PERSIST_BUCKET が未設定です。", "lock_name": "", "payload": {}}

  client = storage_client if storage_client is not None else _build_storage_client()
  bucket = client.bucket(bucket_name)
  lock_name = _lock_object_name(object_prefix, signature)
  blob = bucket.blob(lock_name)
  current_time = now or datetime.now().astimezone()
  payload = {
    "schema_version": LOCK_SCHEMA_VERSION,
    "watch_profile_signature": signature,
    "weekly_run_id": str(run_id or "").strip(),
    "started_at": current_time.isoformat(timespec="seconds"),
    "stale_timeout_seconds": int(stale_timeout_seconds),
  }
  payload_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
  try:
    blob.upload_from_string(
      payload_text,
      content_type="application/json; charset=utf-8",
      if_generation_match=0,
    )
    return {
      "acquired": True,
      "status": "success",
      "message": "cloud lock acquired",
      "bucket": bucket_name,
      "lock_name": lock_name,
      "payload": payload,
      "generation": getattr(blob, "generation", None),
    }
  except Exception:
    existing = _inspect_existing_cloud_lock(blob, now=current_time)
    if not existing.get("exists"):
      return {
        "acquired": False,
        "status": "warning",
        "message": "cloud lock の取得に失敗しました。",
        "bucket": bucket_name,
        "lock_name": lock_name,
        "payload": {},
      }
    if not existing.get("stale"):
      return {
        "acquired": False,
        "status": "blocked",
        "message": str(existing.get("message", "") or "同じ Watch Profile の cloud lock が存在します。"),
        "bucket": bucket_name,
        "lock_name": lock_name,
        "payload": dict(existing.get("payload", {}) or {}),
        "generation": existing.get("generation"),
      }
    try:
      blob.delete(if_generation_match=existing.get("generation"))
    except Exception:
      return {
        "acquired": False,
        "status": "blocked",
        "message": "stale な cloud lock を置換できませんでした。",
        "bucket": bucket_name,
        "lock_name": lock_name,
        "payload": dict(existing.get("payload", {}) or {}),
        "generation": existing.get("generation"),
      }
    retry_blob = bucket.blob(lock_name)
    retry_blob.upload_from_string(
      payload_text,
      content_type="application/json; charset=utf-8",
      if_generation_match=0,
    )
    return {
      "acquired": True,
      "status": "success",
      "message": "cloud stale lock replaced",
      "bucket": bucket_name,
      "lock_name": lock_name,
      "payload": payload,
      "generation": getattr(retry_blob, "generation", None),
      "warnings": [str(existing.get("message", "") or "stale lock replaced")],
    }


def release_cloud_weekly_lock(
  lock_info: dict[str, Any],
  *,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  info = dict(lock_info or {})
  bucket_name = str(info.get("bucket", "") or "").strip()
  lock_name = str(info.get("lock_name", "") or "").strip()
  requested_run_id = str(dict(info.get("payload", {}) or {}).get("weekly_run_id", "") or str(info.get("weekly_run_id", "") or "")).strip()
  if not bucket_name or not lock_name:
    return {"released": False, "status": "ignored", "message": "cloud lock 情報が不足しています。"}
  client = storage_client if storage_client is not None else _build_storage_client()
  bucket = client.bucket(bucket_name)
  blob = bucket.blob(lock_name)
  existing = _inspect_existing_cloud_lock(blob, now=datetime.now().astimezone())
  if not existing.get("exists"):
    return {"released": False, "status": "ignored", "message": "cloud lock は存在しません。"}
  current_run_id = str(dict(existing.get("payload", {}) or {}).get("weekly_run_id", "") or "").strip()
  if not requested_run_id or current_run_id != requested_run_id:
    return {"released": False, "status": "ignored", "message": "他 run の cloud lock は削除しません。"}
  try:
    blob.delete(if_generation_match=existing.get("generation"))
  except Exception as exc:  # noqa: BLE001
    return {"released": False, "status": "warning", "message": f"cloud lock 解放に失敗しました: {type(exc).__name__}"}
  return {"released": True, "status": "success", "message": "cloud lock released"}


def _inspect_existing_cloud_lock(blob: Any, *, now: datetime) -> dict[str, Any]:
  try:
    exists = bool(blob.exists())
  except Exception:
    exists = False
  if not exists:
    return {"exists": False, "stale": False, "payload": {}, "generation": None, "message": ""}
  blob.reload()
  try:
    payload = json.loads(blob.download_as_text(encoding="utf-8"))
  except Exception:  # noqa: BLE001
    payload = {}
  started_at = _parse_iso_datetime(str(dict(payload or {}).get("started_at", "") or ""))
  stale_timeout = int(dict(payload or {}).get("stale_timeout_seconds", 21600) or 21600)
  is_stale = started_at is not None and now >= started_at + timedelta(seconds=max(stale_timeout, 1))
  message = "stale cloud lock" if is_stale else "同じ Watch Profile の cloud lock が存在します。"
  return {
    "exists": True,
    "stale": is_stale,
    "payload": dict(payload or {}),
    "generation": getattr(blob, "generation", None),
    "message": message,
  }


def _lock_object_name(prefix: str, signature: str) -> str:
  normalized_prefix = str(prefix or "weekly_locks").strip().strip("/")
  if not normalized_prefix:
    normalized_prefix = "weekly_locks"
  return f"{normalized_prefix}/{signature}.lock"


def _parse_iso_datetime(value: str) -> datetime | None:
  text = str(value or "").strip()
  if not text:
    return None
  try:
    return datetime.fromisoformat(text)
  except ValueError:
    return None


def _build_storage_client():
  from google.cloud import storage

  return storage.Client()


__all__ = [
  "LOCK_SCHEMA_VERSION",
  "acquire_cloud_weekly_lock",
  "release_cloud_weekly_lock",
]
