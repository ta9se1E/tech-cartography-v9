"""BigQuery admin runner safety gates (Phase 27Q.1)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
  raw = os.environ.get(name)
  if raw is None:
    return default
  return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
  raw = os.environ.get(name)
  if raw is None or not str(raw).strip():
    return default
  try:
    return int(str(raw).strip())
  except ValueError:
    return default


@dataclass(frozen=True)
class BigQuerySafetyConfig:
  enable_bigquery_run: bool
  show_bigquery_admin: bool
  bigquery_project_id: str
  bigquery_location: str
  bigquery_max_bytes_billed: int
  bigquery_default_limit: int
  bigquery_dry_run_only: bool
  bigquery_allow_execute: bool

  @classmethod
  def from_env(cls) -> BigQuerySafetyConfig:
    return cls(
      enable_bigquery_run=_env_bool("ENABLE_BIGQUERY_RUN", False),
      show_bigquery_admin=_env_bool("SHOW_BIGQUERY_ADMIN", False),
      bigquery_project_id=str(os.environ.get("BIGQUERY_PROJECT_ID") or "").strip(),
      bigquery_location=str(os.environ.get("BIGQUERY_LOCATION") or "US").strip() or "US",
      bigquery_max_bytes_billed=_env_int("BIGQUERY_MAX_BYTES_BILLED", 0),
      bigquery_default_limit=min(1000, _env_int("BIGQUERY_DEFAULT_LIMIT", 1000)),
      bigquery_dry_run_only=_env_bool("BIGQUERY_DRY_RUN_ONLY", True),
      bigquery_allow_execute=_env_bool("BIGQUERY_ALLOW_EXECUTE", False),
    )


def can_show_bigquery_admin(config: BigQuerySafetyConfig | None = None) -> bool:
  cfg = config or BigQuerySafetyConfig.from_env()
  return cfg.show_bigquery_admin and cfg.enable_bigquery_run


def can_generate_sql_only(config: BigQuerySafetyConfig | None = None) -> bool:
  return True


def assert_dry_run_allowed(config: BigQuerySafetyConfig | None = None) -> None:
  cfg = config or BigQuerySafetyConfig.from_env()
  if not cfg.enable_bigquery_run:
    raise PermissionError("ENABLE_BIGQUERY_RUN=false — BigQuery dry_run は拒否されました。")
  if cfg.bigquery_max_bytes_billed <= 0:
    raise PermissionError("BIGQUERY_MAX_BYTES_BILLED が未設定 — dry_run は拒否されました。")


def assert_execute_allowed(config: BigQuerySafetyConfig | None = None) -> None:
  cfg = config or BigQuerySafetyConfig.from_env()
  if not cfg.enable_bigquery_run:
    raise PermissionError("ENABLE_BIGQUERY_RUN=false — BigQuery execute は拒否されました。")
  if not cfg.bigquery_allow_execute:
    raise PermissionError("BIGQUERY_ALLOW_EXECUTE=false — execute は拒否されました。")
  if cfg.bigquery_dry_run_only:
    raise PermissionError("BIGQUERY_DRY_RUN_ONLY=true — execute は拒否されました。")
  if cfg.bigquery_max_bytes_billed <= 0:
    raise PermissionError("BIGQUERY_MAX_BYTES_BILLED が未設定 — execute は拒否されました。")


def clamp_limit(limit: int, config: BigQuerySafetyConfig | None = None) -> int:
  cfg = config or BigQuerySafetyConfig.from_env()
  cap = min(1000, cfg.bigquery_default_limit)
  return min(max(1, int(limit)), cap)
