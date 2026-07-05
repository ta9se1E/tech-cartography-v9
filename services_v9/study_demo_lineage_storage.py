"""GCS persistence for Study Demo theme lineage artifacts."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

THEMES_PREFIX = "themes/"
WATCH_PROFILES_PREFIX = "watch_profiles/"
SEARCH_PLANS_PREFIX = "search_plans/"


def _safe_id(value: str) -> str:
  return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or ""))


def theme_version_path(theme_id: str, version: int = 1) -> str:
  return f"{THEMES_PREFIX}{_safe_id(theme_id)}/versions/v{int(version)}.json"


def theme_latest_path(theme_id: str) -> str:
  return f"{THEMES_PREFIX}{_safe_id(theme_id)}/latest.json"


def watch_profile_version_path(watch_profile_id: str, version: int = 1) -> str:
  return f"{WATCH_PROFILES_PREFIX}{_safe_id(watch_profile_id)}/versions/v{int(version)}.json"


def watch_profile_latest_path(watch_profile_id: str) -> str:
  return f"{WATCH_PROFILES_PREFIX}{_safe_id(watch_profile_id)}/latest.json"


def search_plan_version_path(search_plan_id: str, version: int = 1) -> str:
  return f"{SEARCH_PLANS_PREFIX}{_safe_id(search_plan_id)}/versions/v{int(version)}.json"


def search_plan_latest_path(search_plan_id: str) -> str:
  return f"{SEARCH_PLANS_PREFIX}{_safe_id(search_plan_id)}/latest.json"


def _dumps(payload: Mapping[str, Any]) -> str:
  return json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"


def _build_client():
  from google.cloud import storage

  return storage.Client()


def _upload_json(
  bucket_name: str,
  path: str,
  payload: Mapping[str, Any],
  *,
  storage_client: Any | None = None,
) -> None:
  client = storage_client if storage_client is not None else _build_client()
  blob = client.bucket(bucket_name).blob(path)
  blob.upload_from_string(_dumps(payload), content_type="application/json")


def load_json_object(
  path: str,
  *,
  bucket_name: str,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  client = storage_client if storage_client is not None else _build_client()
  blob = client.bucket(bucket_name).blob(path)
  if not blob.exists():
    raise FileNotFoundError(path)
  return dict(json.loads(blob.download_as_bytes().decode("utf-8")))


def save_theme_lineage_object(
  theme: Mapping[str, Any],
  *,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  from services_v9.study_demo_config import get_study_demo_bucket
  from services_v9.study_demo_storage import validate_study_demo_write_target

  bucket_name = get_study_demo_bucket(environ)
  validate_study_demo_write_target(bucket_name, environ=environ)
  theme_id = str(theme.get("theme_id", "") or "")
  version = int(theme.get("theme_version", 1) or 1)
  version_path = theme_version_path(theme_id, version)
  latest_path = theme_latest_path(theme_id)
  _upload_json(bucket_name, version_path, theme, storage_client=storage_client)
  _upload_json(bucket_name, latest_path, theme, storage_client=storage_client)
  return {"status": "saved", "version_path": version_path, "latest_path": latest_path}


def save_watch_profile_lineage_object(
  profile: Mapping[str, Any],
  *,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  from services_v9.study_demo_config import get_study_demo_bucket
  from services_v9.study_demo_storage import validate_study_demo_write_target

  bucket_name = get_study_demo_bucket(environ)
  validate_study_demo_write_target(bucket_name, environ=environ)
  profile_id = str(profile.get("watch_profile_id", "") or "")
  version = int(profile.get("watch_profile_version", 1) or 1)
  version_path = watch_profile_version_path(profile_id, version)
  latest_path = watch_profile_latest_path(profile_id)
  _upload_json(bucket_name, version_path, profile, storage_client=storage_client)
  _upload_json(bucket_name, latest_path, profile, storage_client=storage_client)
  return {"status": "saved", "version_path": version_path, "latest_path": latest_path}


def save_search_plan_lineage_object(
  plan: Mapping[str, Any],
  *,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  from services_v9.study_demo_config import get_study_demo_bucket
  from services_v9.study_demo_storage import validate_study_demo_write_target

  bucket_name = get_study_demo_bucket(environ)
  validate_study_demo_write_target(bucket_name, environ=environ)
  plan_id = str(plan.get("search_plan_id", "") or "")
  version = int(plan.get("search_plan_version", 1) or 1)
  version_path = search_plan_version_path(plan_id, version)
  latest_path = search_plan_latest_path(plan_id)
  _upload_json(bucket_name, version_path, plan, storage_client=storage_client)
  _upload_json(bucket_name, latest_path, plan, storage_client=storage_client)
  return {"status": "saved", "version_path": version_path, "latest_path": latest_path}


__all__ = [
  "load_json_object",
  "save_search_plan_lineage_object",
  "save_theme_lineage_object",
  "save_watch_profile_lineage_object",
  "search_plan_latest_path",
  "search_plan_version_path",
  "theme_latest_path",
  "theme_version_path",
  "watch_profile_latest_path",
  "watch_profile_version_path",
]
