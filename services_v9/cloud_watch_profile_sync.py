"""Safe plan/apply helpers for syncing the v9 cloud watch profile."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .cloud_runtime import get_google_cloud_project, get_persist_bucket_name
from .persistence import load_watch_profile, save_watch_profile
from .retrieval_run_store import stable_payload_signature
from .watch_profile_schema import migrate_watch_profile, watch_profile_summary

DEFAULT_CLOUD_PROJECT = "devops-ai-agent-hackathon-2026"
DEFAULT_CLOUD_BUCKET = "tech-cartography-v9-weekly-persist-1020686343587"
DEFAULT_CLOUD_WATCH_PROFILE_OBJECT = "watch_profile_current.json"
DEFAULT_SOURCE_PROFILE_PATH = Path(__file__).resolve().parents[1] / "data" / "demo" / "v9_demo_watch_profile.json"
MISSING_SIGNATURE = "missing"


def resolve_cloud_watch_profile_target(environ: Mapping[str, str] | None = None) -> dict[str, str]:
  env = environ if environ is not None else os.environ
  project = get_google_cloud_project(env) or DEFAULT_CLOUD_PROJECT
  bucket = get_persist_bucket_name(env) or DEFAULT_CLOUD_BUCKET
  object_name = DEFAULT_CLOUD_WATCH_PROFILE_OBJECT
  return {
    "project": project,
    "bucket": bucket,
    "object_name": object_name,
    "uri": f"gs://{bucket}/{object_name}",
  }


def load_source_watch_profile(source_path: Path | str | None = None) -> dict[str, Any]:
  path = Path(source_path) if source_path is not None else DEFAULT_SOURCE_PROFILE_PATH
  payload = json.loads(path.read_text(encoding="utf-8"))
  normalized = migrate_watch_profile(dict(payload or {}))
  return {
    "path": str(path.resolve()),
    "profile": normalized,
    "signature": stable_payload_signature(normalized),
    "summary": watch_profile_summary(normalized),
  }


def load_cloud_watch_profile(
  *,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  target = resolve_cloud_watch_profile_target(environ)
  client = storage_client if storage_client is not None else _build_storage_client(project=target["project"])
  bucket = client.bucket(target["bucket"])
  blob = bucket.blob(target["object_name"])
  if not blob.exists():
    return {
      **target,
      "exists": False,
      "profile": None,
      "signature": MISSING_SIGNATURE,
      "summary": {},
      "generation": None,
      "raw_text": "",
      "status": "missing",
    }
  if hasattr(blob, "reload"):
    blob.reload()
  raw_text = blob.download_as_text(encoding="utf-8")
  payload = json.loads(raw_text)
  normalized = migrate_watch_profile(dict(payload or {}))
  return {
    **target,
    "exists": True,
    "profile": normalized,
    "signature": stable_payload_signature(normalized),
    "summary": watch_profile_summary(normalized),
    "generation": getattr(blob, "generation", None),
    "raw_text": raw_text,
    "status": "existing",
  }


def summarize_watch_profile_diff(
  current_profile: Mapping[str, Any] | None,
  source_profile: Mapping[str, Any],
) -> dict[str, Any]:
  if current_profile is None:
    source_summary = watch_profile_summary(dict(source_profile or {}))
    return {
      "top_level_keys_changed": sorted(dict(source_profile or {}).keys()),
      "missing_in_cloud": sorted(dict(source_profile or {}).keys()),
      "missing_in_source": [],
      "type_differences": [],
      "order_only": [],
      "list_differences": [],
      "value_differences": [],
      "diff_count": len(dict(source_profile or {})),
      "notes": [
        "cloud watch profile object is missing",
        "theme_name=" + str(source_summary.get("theme_name", "") or ""),
      ],
    }

  diffs = _diff_mappings(dict(current_profile or {}), dict(source_profile or {}))
  return {
    "top_level_keys_changed": sorted({path.split(".", 1)[0] for path, _, _, _ in diffs}),
    "missing_in_cloud": [path for path, kind, _, _ in diffs if kind == "missing_in_cloud"],
    "missing_in_source": [path for path, kind, _, _ in diffs if kind == "missing_in_source"],
    "type_differences": [path for path, kind, _, _ in diffs if kind.startswith("type:")],
    "order_only": [path for path, kind, _, _ in diffs if kind == "order_only"],
    "list_differences": [path for path, kind, _, _ in diffs if kind == "list_diff"],
    "value_differences": [path for path, kind, _, _ in diffs if kind == "value_diff"],
    "diff_count": len(diffs),
    "notes": [],
  }


def plan_cloud_watch_profile_sync(
  *,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  source = load_source_watch_profile()
  current = load_cloud_watch_profile(environ=environ, storage_client=storage_client)
  backup_object = build_watch_profile_backup_object_name(current_signature=current["signature"])
  return {
    "status": "ok",
    "mode": "plan",
    "source_path": source["path"],
    "source_signature": source["signature"],
    "current_signature": current["signature"],
    "current_status": current["status"],
    "destination_uri": current["uri"],
    "backup_uri": f"gs://{current['bucket']}/{backup_object}",
    "diff_summary": summarize_watch_profile_diff(current.get("profile"), source["profile"]),
  }


def apply_cloud_watch_profile_sync(
  *,
  expected_current_signature: str,
  expected_source_signature: str,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
  now: datetime | None = None,
) -> dict[str, Any]:
  env = dict(environ or os.environ)
  if str(env.get("V9_CLOUD_CHANGE_APPROVED", "") or "").strip().lower() != "true":
    return {"status": "blocked", "message": "V9_CLOUD_CHANGE_APPROVED=true が必要です。"}

  source = load_source_watch_profile()
  current = load_cloud_watch_profile(environ=env, storage_client=storage_client)
  if source["signature"] != str(expected_source_signature or "").strip():
    return {
      "status": "blocked",
      "message": "source signature mismatch",
      "source_signature": source["signature"],
      "expected_source_signature": str(expected_source_signature or "").strip(),
    }
  if current["signature"] != str(expected_current_signature or "").strip():
    return {
      "status": "blocked",
      "message": "current signature mismatch",
      "current_signature": current["signature"],
      "expected_current_signature": str(expected_current_signature or "").strip(),
    }

  target = resolve_cloud_watch_profile_target(env)
  client = storage_client if storage_client is not None else _build_storage_client(project=target["project"])
  backup_object = build_watch_profile_backup_object_name(
    current_signature=current["signature"],
    now=now,
  )
  try:
    _write_backup_before_sync(
      client=client,
      bucket_name=target["bucket"],
      backup_object=backup_object,
      current=current,
      now=now,
    )

    serialized_profile = _build_serialized_source_profile(source["profile"])
    _write_cloud_watch_profile(
      client=client,
      bucket_name=target["bucket"],
      object_name=target["object_name"],
      serialized_profile=serialized_profile,
      if_generation_match=current.get("generation"),
    )
    reloaded = load_cloud_watch_profile(environ=env, storage_client=client)
    if reloaded["signature"] != source["signature"]:
      return {
        "status": "failed",
        "message": "saved cloud watch profile signature mismatch",
        "saved_signature": reloaded["signature"],
        "expected_signature": source["signature"],
        "backup_uri": f"gs://{target['bucket']}/{backup_object}",
        "destination_uri": target["uri"],
      }
    return {
      "status": "success",
      "message": "cloud watch profile synced",
      "source_signature": source["signature"],
      "current_signature_before": current["signature"],
      "current_signature_after": reloaded["signature"],
      "backup_uri": f"gs://{target['bucket']}/{backup_object}",
      "destination_uri": target["uri"],
    }
  except Exception as exc:  # noqa: BLE001
    return {
      "status": "failed",
      "message": str(exc),
      "backup_uri": f"gs://{target['bucket']}/{backup_object}",
      "destination_uri": target["uri"],
    }


def build_watch_profile_backup_object_name(
  *,
  current_signature: str,
  now: datetime | None = None,
) -> str:
  stamp = (now or datetime.now().astimezone()).strftime("%Y%m%d_%H%M%S")
  suffix = str(current_signature or MISSING_SIGNATURE).strip() or MISSING_SIGNATURE
  return f"watch_profile_backups/{stamp}_{suffix}.json"


def _build_serialized_source_profile(source_profile: Mapping[str, Any]) -> str:
  with tempfile.TemporaryDirectory() as tmp_dir:
    root = Path(tmp_dir) / "v9_runs"
    save_watch_profile(dict(source_profile or {}), base_dir=root)
    reloaded = load_watch_profile(base_dir=root)
    return json.dumps(reloaded, ensure_ascii=False, indent=2) + "\n"


def _write_backup_before_sync(
  *,
  client: Any,
  bucket_name: str,
  backup_object: str,
  current: Mapping[str, Any],
  now: datetime | None,
) -> None:
  backup_blob = client.bucket(bucket_name).blob(backup_object)
  if current.get("exists"):
    backup_text = str(current.get("raw_text", "") or "")
  else:
    backup_text = json.dumps(
      {
        "status": "missing",
        "object_name": str(current.get("object_name", "") or ""),
        "observed_at": (now or datetime.now().astimezone()).isoformat(timespec="seconds"),
        "signature": MISSING_SIGNATURE,
      },
      ensure_ascii=False,
      indent=2,
    ) + "\n"
  backup_blob.upload_from_string(
    backup_text,
    content_type="application/json; charset=utf-8",
    if_generation_match=0,
  )


def _write_cloud_watch_profile(
  *,
  client: Any,
  bucket_name: str,
  object_name: str,
  serialized_profile: str,
  if_generation_match: Any,
) -> None:
  blob = client.bucket(bucket_name).blob(object_name)
  upload_kwargs: dict[str, Any] = {}
  if if_generation_match is None:
    upload_kwargs["if_generation_match"] = 0
  else:
    upload_kwargs["if_generation_match"] = int(if_generation_match)
  blob.upload_from_string(
    serialized_profile,
    content_type="application/json; charset=utf-8",
    **upload_kwargs,
  )


def _build_storage_client(*, project: str):
  from google.cloud import storage

  return storage.Client(project=project)


def _diff_mappings(
  current: Mapping[str, Any],
  source: Mapping[str, Any],
  prefix: str = "",
) -> list[tuple[str, str, Any, Any]]:
  diffs: list[tuple[str, str, Any, Any]] = []
  keys = set(current) | set(source)
  for key in sorted(keys):
    path = f"{prefix}.{key}" if prefix else key
    if key not in current:
      diffs.append((path, "missing_in_cloud", None, source[key]))
      continue
    if key not in source:
      diffs.append((path, "missing_in_source", current[key], None))
      continue
    left = current[key]
    right = source[key]
    if isinstance(left, dict) and isinstance(right, dict):
      diffs.extend(_diff_mappings(left, right, path))
      continue
    if type(left) is not type(right):
      diffs.append((path, f"type:{type(left).__name__}->{type(right).__name__}", left, right))
      continue
    if isinstance(left, list) and isinstance(right, list):
      if left == right:
        continue
      if _sorted_json_items(left) == _sorted_json_items(right):
        diffs.append((path, "order_only", len(left), len(right)))
      else:
        diffs.append((path, "list_diff", len(left), len(right)))
      continue
    if left != right:
      diffs.append((path, "value_diff", left, right))
  return diffs


def _sorted_json_items(values: list[Any]) -> list[str]:
  return sorted(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in values)


__all__ = [
  "DEFAULT_CLOUD_BUCKET",
  "DEFAULT_CLOUD_PROJECT",
  "DEFAULT_CLOUD_WATCH_PROFILE_OBJECT",
  "DEFAULT_SOURCE_PROFILE_PATH",
  "MISSING_SIGNATURE",
  "apply_cloud_watch_profile_sync",
  "build_watch_profile_backup_object_name",
  "load_cloud_watch_profile",
  "load_source_watch_profile",
  "plan_cloud_watch_profile_sync",
  "resolve_cloud_watch_profile_target",
  "summarize_watch_profile_diff",
]
