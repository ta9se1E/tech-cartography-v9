"""Global search lock for study demo."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from services_v9.study_demo_config import get_study_demo_bucket

from .constants import SEARCH_LOCK_OBJECT

LOCK_SCHEMA_VERSION = "v9.7c"
DEFAULT_STALE_SECONDS = 1800


def acquire_search_lock(
  search_run_id: str,
  *,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
  owner_id: str | None = None,
  stale_timeout_seconds: int = DEFAULT_STALE_SECONDS,
  now: datetime | None = None,
) -> dict[str, Any]:
  bucket_name = get_study_demo_bucket(environ)
  client = storage_client if storage_client is not None else _build_client()
  bucket = client.bucket(bucket_name)
  blob = bucket.blob(SEARCH_LOCK_OBJECT)
  current = now or datetime.now(timezone.utc)
  owner = owner_id or uuid.uuid4().hex
  payload = {
    "schema_version": LOCK_SCHEMA_VERSION,
    "owner_id": owner,
    "search_run_id": search_run_id,
    "acquired_at": current.isoformat(),
    "expires_at": (current + timedelta(seconds=stale_timeout_seconds)).isoformat(),
    "stale_timeout_seconds": stale_timeout_seconds,
  }
  text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
  try:
    blob.upload_from_string(text, content_type="application/json", if_generation_match=0)
    return {"acquired": True, "owner_id": owner, "bucket": bucket_name, "lock_name": SEARCH_LOCK_OBJECT, "payload": payload, "generation": getattr(blob, "generation", None)}
  except Exception:
    existing = _inspect_lock(blob, now=current)
    if existing.get("stale"):
      try:
        blob.delete(if_generation_match=existing.get("generation"))
      except Exception:
        return {"acquired": False, "message": "stale lock replacement failed", "payload": existing.get("payload", {})}
      retry = bucket.blob(SEARCH_LOCK_OBJECT)
      retry.upload_from_string(text, content_type="application/json", if_generation_match=0)
      return {"acquired": True, "owner_id": owner, "bucket": bucket_name, "lock_name": SEARCH_LOCK_OBJECT, "payload": payload, "generation": getattr(retry, "generation", None)}
    return {"acquired": False, "message": "search lock already held", "payload": existing.get("payload", {})}


def release_search_lock(lock_info: Mapping[str, Any], *, storage_client: Any | None = None) -> dict[str, Any]:
  bucket_name = str(lock_info.get("bucket", "") or get_study_demo_bucket())
  owner_id = str(dict(lock_info.get("payload", {}) or {}).get("owner_id", lock_info.get("owner_id", "")) or "")
  client = storage_client if storage_client is not None else _build_client()
  blob = client.bucket(bucket_name).blob(SEARCH_LOCK_OBJECT)
  existing = _inspect_lock(blob)
  if not existing.get("exists"):
    return {"released": False, "status": "ignored"}
  current_owner = str(dict(existing.get("payload", {}) or {}).get("owner_id", "") or "")
  if owner_id and current_owner != owner_id:
    return {"released": False, "status": "ignored", "message": "owner mismatch"}
  blob.delete(if_generation_match=existing.get("generation"))
  return {"released": True, "status": "success"}


def _inspect_lock(blob: Any, *, now: datetime | None = None) -> dict[str, Any]:
  if not blob.exists():
    return {"exists": False, "stale": False, "payload": {}, "generation": None}
  blob.reload()
  payload = json.loads(blob.download_as_bytes().decode("utf-8"))
  current = now or datetime.now(timezone.utc)
  expires_raw = str(payload.get("expires_at", "") or "")
  stale = False
  if expires_raw:
    try:
      expires_at = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
      stale = current >= expires_at
    except ValueError:
      stale = False
  return {"exists": True, "stale": stale, "payload": payload, "generation": getattr(blob, "generation", None)}


def _build_client():
  from google.cloud import storage

  return storage.Client()
