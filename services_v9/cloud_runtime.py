"""Runtime configuration helpers for Tech Cartography v9 cloud migration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_MODE = "local"
DEFAULT_PERSIST_ROOT = "data/v9_runs"
DEFAULT_WEEKLY_CONFIG_OBJECT = "v9_config/weekly_delivery_config.json"


def get_runtime_mode(environ: Mapping[str, str] | None = None) -> str:
  env = environ if environ is not None else os.environ
  value = str(env.get("V9_RUNTIME_MODE", DEFAULT_RUNTIME_MODE) or DEFAULT_RUNTIME_MODE).strip().lower()
  return "cloud" if value == "cloud" else "local"


def is_cloud_runtime(environ: Mapping[str, str] | None = None) -> bool:
  return get_runtime_mode(environ) == "cloud"


def get_persist_root(environ: Mapping[str, str] | None = None) -> Path:
  env = environ if environ is not None else os.environ
  raw_value = str(env.get("V9_PERSIST_ROOT", DEFAULT_PERSIST_ROOT) or DEFAULT_PERSIST_ROOT).strip()
  requested = Path(raw_value)
  if requested.is_absolute():
    return requested.resolve()
  return (PROJECT_ROOT / requested).resolve()


def get_persist_bucket_name(environ: Mapping[str, str] | None = None) -> str:
  env = environ if environ is not None else os.environ
  return str(env.get("V9_PERSIST_BUCKET", "") or "").strip()


def get_weekly_config_object_name(environ: Mapping[str, str] | None = None) -> str:
  env = environ if environ is not None else os.environ
  return str(env.get("V9_WEEKLY_CONFIG_OBJECT", DEFAULT_WEEKLY_CONFIG_OBJECT) or DEFAULT_WEEKLY_CONFIG_OBJECT).strip()


def get_cloud_region(environ: Mapping[str, str] | None = None) -> str:
  env = environ if environ is not None else os.environ
  return str(env.get("V9_CLOUD_REGION", "") or "").strip()


def get_scheduler_region(environ: Mapping[str, str] | None = None) -> str:
  env = environ if environ is not None else os.environ
  return str(env.get("V9_SCHEDULER_REGION", "") or get_cloud_region(env)).strip()


def get_scheduler_job_name(environ: Mapping[str, str] | None = None) -> str:
  env = environ if environ is not None else os.environ
  return str(env.get("V9_SCHEDULER_JOB_NAME", "") or "").strip()


def get_weekly_job_name(environ: Mapping[str, str] | None = None) -> str:
  env = environ if environ is not None else os.environ
  return str(env.get("V9_WEEKLY_JOB_NAME", "") or "").strip()


def get_service_name(environ: Mapping[str, str] | None = None) -> str:
  env = environ if environ is not None else os.environ
  return str(env.get("V9_STREAMLIT_SERVICE_NAME", "") or "").strip()


def get_google_cloud_project(environ: Mapping[str, str] | None = None) -> str:
  env = environ if environ is not None else os.environ
  for name in ("GOOGLE_CLOUD_PROJECT", "GCP_PROJECT"):
    value = str(env.get(name, "") or "").strip()
    if value:
      return value
  return ""


def get_scheduler_service_account(environ: Mapping[str, str] | None = None) -> str:
  env = environ if environ is not None else os.environ
  return str(env.get("V9_SCHEDULER_SERVICE_ACCOUNT", "") or "").strip()


def is_cloud_scheduler_admin_enabled(environ: Mapping[str, str] | None = None) -> bool:
  env = environ if environ is not None else os.environ
  return _env_bool(env, "V9_ENABLE_CLOUD_SCHEDULER_ADMIN", False)


def _env_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
  value = str(env.get(name, "") or "").strip().lower()
  if value in {"1", "true", "yes", "on"}:
    return True
  if value in {"0", "false", "no", "off"}:
    return False
  return default


__all__ = [
  "DEFAULT_PERSIST_ROOT",
  "DEFAULT_RUNTIME_MODE",
  "DEFAULT_WEEKLY_CONFIG_OBJECT",
  "PROJECT_ROOT",
  "get_cloud_region",
  "get_google_cloud_project",
  "get_persist_bucket_name",
  "get_persist_root",
  "get_runtime_mode",
  "get_scheduler_job_name",
  "get_scheduler_region",
  "get_scheduler_service_account",
  "get_service_name",
  "get_weekly_config_object_name",
  "get_weekly_job_name",
  "is_cloud_runtime",
  "is_cloud_scheduler_admin_enabled",
]
