"""Configuration helpers for the isolated v9 study demo Cloud Run service."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Mapping

PRODUCTION_PERSIST_BUCKET = "tech-cartography-v9-weekly-persist-1020686343587"
STUDY_DEMO_BUCKET_DEFAULT = "tech-cartography-v9-study-demo-1020686343587"
STUDY_DEMO_SERVICE_NAME = "tech-cartography-v9-study-demo"
STUDY_DEMO_SERVICE_ACCOUNT = (
  "tech-cartography-v9-study-demo@devops-ai-agent-hackathon-2026.iam.gserviceaccount.com"
)
STUDY_DEMO_PASSWORD_SECRET = "tech-cartography-v9-study-demo-password"
STUDY_DEMO_OPENALEX_SECRET = "tech-cartography-v9-study-demo-openalex-api-key"
STUDY_DEMO_TAVILY_SECRET = "tech-cartography-v9-study-demo-tavily-api-key"
STUDY_DEMO_PROJECT_DEFAULT = "devops-ai-agent-hackathon-2026"
STUDY_DEMO_REGION_DEFAULT = "us-central1"
STUDY_DEMO_BQ_MAX_BYTES_BILLED_DEFAULT = 2_199_023_255_552
STUDY_DEMO_BQ_PRICE_PER_TIB_USD_DEFAULT = 6.25

PRODUCTION_SECRET_DENYLIST = frozenset(
  {
    "tech-cartography-smtp-password",
    "tech-cartography-tavily-api-key",
  }
)

SEED_PREFIX = "seed/"
ACTIVE_PREFIX = "active/"
RESET_HISTORY_PREFIX = "reset_history/"

SOURCE_RUN_ID_DEFAULT = "cloud_weekly_job_20260704_181253"


def _env_bool(env: Mapping[str, str], name: str, default: bool = False) -> bool:
  value = str(env.get(name, "") or "").strip().lower()
  if value in {"1", "true", "yes", "on"}:
    return True
  if value in {"0", "false", "no", "off"}:
    return False
  return default


def is_study_demo_mode(environ: Mapping[str, str] | None = None) -> bool:
  env = environ if environ is not None else os.environ
  return _env_bool(env, "V9_STUDY_DEMO_MODE", False)


def is_study_demo_external_execution_disabled(environ: Mapping[str, str] | None = None) -> bool:
  env = environ if environ is not None else os.environ
  if not is_study_demo_mode(env):
    return False
  return _env_bool(env, "V9_STUDY_DEMO_DISABLE_EXTERNAL_EXECUTION", True)


def is_study_demo_shared_state(environ: Mapping[str, str] | None = None) -> bool:
  env = environ if environ is not None else os.environ
  if not is_study_demo_mode(env):
    return False
  return _env_bool(env, "V9_STUDY_DEMO_SHARED_STATE", True)


def get_study_demo_bucket(environ: Mapping[str, str] | None = None) -> str:
  env = environ if environ is not None else os.environ
  return str(env.get("V9_STUDY_DEMO_BUCKET", STUDY_DEMO_BUCKET_DEFAULT) or STUDY_DEMO_BUCKET_DEFAULT).strip()


def get_study_demo_password(environ: Mapping[str, str] | None = None) -> str:
  from .study_demo_access import is_public_demo

  if is_public_demo(environ):
    return ""
  env = environ if environ is not None else os.environ
  return str(env.get("V9_STUDY_DEMO_PASSWORD", "") or "").strip()


def get_study_demo_expires_at(environ: Mapping[str, str] | None = None) -> datetime | None:
  env = environ if environ is not None else os.environ
  raw = str(env.get("V9_STUDY_DEMO_EXPIRES_AT", "") or "").strip()
  if not raw:
    return None
  normalized = raw.replace("Z", "+00:00")
  try:
    parsed = datetime.fromisoformat(normalized)
  except ValueError:
    return None
  if parsed.tzinfo is None:
    parsed = parsed.replace(tzinfo=timezone.utc)
  return parsed.astimezone(timezone.utc)


def is_study_demo_expired(
  *,
  environ: Mapping[str, str] | None = None,
  now: datetime | None = None,
) -> bool:
  if not is_study_demo_mode(environ):
    return False
  expires_at = get_study_demo_expires_at(environ)
  if expires_at is None:
    return False
  current = now or datetime.now(timezone.utc)
  return current >= expires_at


def is_study_demo_password_configured(environ: Mapping[str, str] | None = None) -> bool:
  return bool(get_study_demo_password(environ))


def is_study_demo_search_enabled(environ: Mapping[str, str] | None = None) -> bool:
  env = environ if environ is not None else os.environ
  if not is_study_demo_mode(env):
    return False
  return _env_bool(env, "V9_STUDY_DEMO_SEARCH_ENABLED", False)


def is_study_demo_patent_search_enabled(environ: Mapping[str, str] | None = None) -> bool:
  env = environ if environ is not None else os.environ
  return is_study_demo_search_enabled(env) and _env_bool(env, "V9_STUDY_DEMO_ENABLE_PATENT_SEARCH", False)


def is_study_demo_paper_search_enabled(environ: Mapping[str, str] | None = None) -> bool:
  env = environ if environ is not None else os.environ
  return is_study_demo_search_enabled(env) and _env_bool(env, "V9_STUDY_DEMO_ENABLE_PAPER_SEARCH", False)


def is_study_demo_web_search_enabled(environ: Mapping[str, str] | None = None) -> bool:
  env = environ if environ is not None else os.environ
  return is_study_demo_search_enabled(env) and _env_bool(env, "V9_STUDY_DEMO_ENABLE_WEB_SEARCH", False)


def get_study_demo_openalex_api_key(environ: Mapping[str, str] | None = None) -> str:
  env = environ if environ is not None else os.environ
  return str(env.get("V9_STUDY_DEMO_OPENALEX_API_KEY", "") or "").strip()


def get_study_demo_tavily_api_key(environ: Mapping[str, str] | None = None) -> str:
  env = environ if environ is not None else os.environ
  return str(env.get("V9_STUDY_DEMO_TAVILY_API_KEY", "") or "").strip()


def get_study_demo_bigquery_max_bytes_billed(environ: Mapping[str, str] | None = None) -> int:
  env = environ if environ is not None else os.environ
  raw = str(env.get("V9_STUDY_DEMO_BIGQUERY_MAX_BYTES_BILLED", "") or "").strip()
  if not raw:
    return STUDY_DEMO_BQ_MAX_BYTES_BILLED_DEFAULT
  try:
    return int(raw)
  except ValueError:
    return STUDY_DEMO_BQ_MAX_BYTES_BILLED_DEFAULT


def get_study_demo_bigquery_price_per_tib_usd(environ: Mapping[str, str] | None = None) -> float:
  env = environ if environ is not None else os.environ
  raw = str(env.get("V9_STUDY_DEMO_BIGQUERY_PRICE_PER_TIB_USD", "") or "").strip()
  if not raw:
    return STUDY_DEMO_BQ_PRICE_PER_TIB_USD_DEFAULT
  try:
    return float(raw)
  except ValueError:
    return STUDY_DEMO_BQ_PRICE_PER_TIB_USD_DEFAULT


def is_study_demo_bigquery_dry_run_first(environ: Mapping[str, str] | None = None) -> bool:
  env = environ if environ is not None else os.environ
  return _env_bool(env, "V9_STUDY_DEMO_BIGQUERY_DRY_RUN_FIRST", True)


def assert_study_demo_bucket_allowed(bucket_name: str, *, environ: Mapping[str, str] | None = None) -> None:
  normalized = str(bucket_name or "").strip()
  if not normalized:
    raise ValueError("study demo bucket name is required")
  if normalized == PRODUCTION_PERSIST_BUCKET:
    raise ValueError("production persist bucket access is forbidden in study demo mode")
  expected = get_study_demo_bucket(environ)
  if normalized != expected:
    raise ValueError("bucket name is not the configured study demo bucket")


__all__ = [
  "ACTIVE_PREFIX",
  "PRODUCTION_PERSIST_BUCKET",
  "RESET_HISTORY_PREFIX",
  "SEED_PREFIX",
  "SOURCE_RUN_ID_DEFAULT",
  "STUDY_DEMO_BUCKET_DEFAULT",
  "STUDY_DEMO_OPENALEX_SECRET",
  "STUDY_DEMO_PASSWORD_SECRET",
  "STUDY_DEMO_PROJECT_DEFAULT",
  "STUDY_DEMO_REGION_DEFAULT",
  "STUDY_DEMO_SERVICE_ACCOUNT",
  "STUDY_DEMO_SERVICE_NAME",
  "STUDY_DEMO_TAVILY_SECRET",
  "PRODUCTION_SECRET_DENYLIST",
  "assert_study_demo_bucket_allowed",
  "get_study_demo_bigquery_max_bytes_billed",
  "get_study_demo_bigquery_price_per_tib_usd",
  "get_study_demo_bucket",
  "get_study_demo_expires_at",
  "get_study_demo_openalex_api_key",
  "get_study_demo_password",
  "get_study_demo_tavily_api_key",
  "is_study_demo_bigquery_dry_run_first",
  "is_study_demo_expired",
  "is_study_demo_external_execution_disabled",
  "is_study_demo_mode",
  "is_study_demo_paper_search_enabled",
  "is_study_demo_password_configured",
  "is_study_demo_patent_search_enabled",
  "is_study_demo_search_enabled",
  "is_study_demo_shared_state",
  "is_study_demo_web_search_enabled",
]
