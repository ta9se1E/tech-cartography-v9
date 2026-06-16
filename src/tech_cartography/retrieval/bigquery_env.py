"""BigQuery environment diagnostics for v7."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

BYTES_PER_GB = 1024**3
BYTES_PER_TB = 1024**4

DIAGNOSTIC_SELECT_1_SQL = "SELECT 1 AS ok"


def usd_to_bytes(usd: float, usd_per_tb: float = 5.0) -> int:
  if usd <= 0:
    return 0
  return int((usd / usd_per_tb) * BYTES_PER_TB)


def gb_to_bytes(gb: float) -> int:
  return int(gb * BYTES_PER_GB)


def bytes_to_gb(num_bytes: int) -> float:
  return num_bytes / BYTES_PER_GB


def estimate_usd_from_bytes(num_bytes: int, usd_per_tb: float = 5.0) -> float:
  return (num_bytes / BYTES_PER_TB) * usd_per_tb


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


def resolve_project_id(explicit_project_id: str | None = None) -> dict[str, Any]:
  """Resolve BigQuery project_id from explicit arg, env, gcloud, or client default."""
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
    "error": (
      "Could not resolve project_id. Set GOOGLE_CLOUD_PROJECT or run "
      "gcloud config set project."
    ),
  }


def _check_result(
  check_name: str,
  *,
  ok: bool,
  message: str,
  suggested_action: str = "",
) -> dict[str, str]:
  return {
    "check_name": check_name,
    "status": "ok" if ok else "error",
    "message": message,
    "suggested_action": suggested_action,
  }


def check_bigquery_environment(project_id: str | None = None) -> dict[str, Any]:
  """Run minimal BigQuery environment diagnostics."""
  checks: list[dict[str, str]] = []

  try:
    from google.cloud import bigquery  # noqa: F401
  except ImportError as exc:
    checks.append(
      _check_result(
        "google_cloud_bigquery_import",
        ok=False,
        message=str(exc),
        suggested_action="pip install google-cloud-bigquery",
      ),
    )
    return {
      "ready": False,
      "project_id": "",
      "checks": checks,
    }

  checks.append(
    _check_result(
      "google_cloud_bigquery_import",
      ok=True,
      message="google-cloud-bigquery import OK",
    ),
  )

  resolved = resolve_project_id(project_id)
  resolved_project = resolved.get("project_id", "")
  if resolved_project:
    checks.append(
      _check_result(
        "project_id_resolution",
        ok=True,
        message=f"project_id={resolved_project} (source={resolved.get('source')})",
      ),
    )
  else:
    checks.append(
      _check_result(
        "project_id_resolution",
        ok=False,
        message=str(resolved.get("error") or "project_id unresolved"),
        suggested_action="Set GOOGLE_CLOUD_PROJECT or pass --project-id",
      ),
    )
    return {"ready": False, "project_id": "", "checks": checks}

  try:
    from google.cloud import bigquery

    client = bigquery.Client(project=resolved_project)
    checks.append(
      _check_result(
        "bigquery_client_init",
        ok=True,
        message=f"BigQuery client initialized for {resolved_project}",
      ),
    )
  except Exception as exc:  # noqa: BLE001
    checks.append(
      _check_result(
        "bigquery_client_init",
        ok=False,
        message=str(exc),
        suggested_action="Check GCP credentials and project permissions",
      ),
    )
    return {"ready": False, "project_id": resolved_project, "checks": checks}

  try:
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=True)
    job = client.query(DIAGNOSTIC_SELECT_1_SQL, job_config=job_config)
    checks.append(
      _check_result(
        "select_1_dry_run",
        ok=True,
        message=f"SELECT 1 dry run OK (total_bytes_processed={job.total_bytes_processed})",
      ),
    )
  except Exception as exc:  # noqa: BLE001
    checks.append(
      _check_result(
        "select_1_dry_run",
        ok=False,
        message=str(exc),
        suggested_action="Verify BigQuery API access and billing for the project",
      ),
    )
    return {"ready": False, "project_id": resolved_project, "checks": checks}

  return {"ready": True, "project_id": resolved_project, "checks": checks}
