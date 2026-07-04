"""Lightweight BigQuery safety helpers for v9 startup-safe imports."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

BYTES_PER_GB = 1024**3
BYTES_PER_TB = 1024**4


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


def bytes_to_gb(num_bytes: int) -> float:
  return int(num_bytes or 0) / BYTES_PER_GB


def estimate_usd_from_bytes(num_bytes: int, usd_per_tb: float = 5.0) -> float:
  return (int(num_bytes or 0) / BYTES_PER_TB) * float(usd_per_tb)


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


def resolve_project_id(explicit_project_id: str | None = None) -> dict[str, Any]:
  """Resolve a project id without importing BigQuery on module import."""
  if explicit_project_id and str(explicit_project_id).strip():
    return {
      "project_id": str(explicit_project_id).strip(),
      "source": "explicit",
      "error": None,
    }

  for env_key in ("GOOGLE_CLOUD_PROJECT", "GCP_PROJECT"):
    value = os.environ.get(env_key, "").strip()
    if value:
      return {"project_id": value, "source": env_key, "error": None}

  gcloud_project = _gcloud_config_project()
  if gcloud_project:
    return {"project_id": gcloud_project, "source": "gcloud_config", "error": None}

  try:
    from google.cloud import bigquery

    client = bigquery.Client()
    if client.project:
      return {
        "project_id": client.project,
        "source": "bigquery_client_default",
        "error": None,
      }
  except Exception as exc:  # noqa: BLE001
    return {"project_id": "", "source": "none", "error": str(exc)}

  return {
    "project_id": "",
    "source": "none",
    "error": "Could not resolve project_id. Set GOOGLE_CLOUD_PROJECT or run gcloud config set project.",
  }


def _gcloud_config_project() -> str:
  if not shutil.which("gcloud"):
    return ""
  try:
    completed = subprocess.run(
      ["gcloud", "config", "get-value", "project"],
      capture_output=True,
      text=True,
      timeout=10,
      check=False,
    )
  except (OSError, subprocess.TimeoutExpired):
    return ""
  project = completed.stdout.strip()
  if project and project != "(unset)":
    return project
  return ""


__all__ = [
  "BigQuerySafetyConfig",
  "assert_dry_run_allowed",
  "assert_execute_allowed",
  "bytes_to_gb",
  "estimate_usd_from_bytes",
  "resolve_project_id",
]
