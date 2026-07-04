"""Cloud Scheduler admin helpers for v9 weekly delivery control."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Callable, Mapping

from .cloud_runtime import (
  get_google_cloud_project,
  get_scheduler_job_name,
  get_scheduler_region,
  is_cloud_scheduler_admin_enabled,
)
from .study_demo_guard import assert_external_execution_allowed

SchedulerCall = Callable[[str, str, dict[str, Any] | None], dict[str, Any]]


def get_scheduler_job_status(
  *,
  environ: Mapping[str, str] | None = None,
  call_api: SchedulerCall | None = None,
) -> dict[str, Any]:
  if not is_cloud_scheduler_admin_enabled(environ):
    return _blocked_response("クラウド管理機能が無効です。")
  project = get_google_cloud_project(environ)
  region = get_scheduler_region(environ)
  job_name = get_scheduler_job_name(environ)
  if not project or not region or not job_name:
    return _blocked_response("Scheduler参照に必要な project / region / job name が未設定です。")
  payload = _call_scheduler_api(
    "GET",
    _job_url(project, region, job_name),
    None,
    call_api=call_api,
  )
  return {
    "status": "success",
    "job_name": job_name,
    "schedule": str(payload.get("schedule", "") or ""),
    "time_zone": str(payload.get("timeZone", "") or ""),
    "state": str(payload.get("state", "") or ""),
    "payload": payload,
  }


def apply_scheduler_settings(
  settings: Mapping[str, Any],
  *,
  environ: Mapping[str, str] | None = None,
  call_api: SchedulerCall | None = None,
) -> dict[str, Any]:
  assert_external_execution_allowed("cloud_scheduler")
  if not is_cloud_scheduler_admin_enabled(environ):
    return _blocked_response("クラウド管理機能が無効です。")
  project = get_google_cloud_project(environ)
  region = get_scheduler_region(environ)
  job_name = get_scheduler_job_name(environ)
  if not project or not region or not job_name:
    return _blocked_response("Scheduler更新に必要な project / region / job name が未設定です。")
  body = {
    "schedule": str(settings.get("cron_expression", "") or ""),
    "timeZone": str(settings.get("timezone", "") or ""),
  }
  patch_url = _job_url(project, region, job_name) + "?updateMask=schedule,timeZone"
  patch_payload = _call_scheduler_api("PATCH", patch_url, body, call_api=call_api)
  enabled = bool(settings.get("enabled", False))
  state_payload = resume_scheduler_job(environ=environ, call_api=call_api) if enabled else pause_scheduler_job(environ=environ, call_api=call_api)
  return {
    "status": "success" if state_payload.get("status") == "success" else state_payload.get("status", "warning"),
    "job_name": job_name,
    "schedule": str(patch_payload.get("schedule", body["schedule"]) or body["schedule"]),
    "time_zone": str(patch_payload.get("timeZone", body["timeZone"]) or body["timeZone"]),
    "state": str(state_payload.get("state", "") or ""),
    "payload": patch_payload,
  }


def pause_scheduler_job(
  *,
  environ: Mapping[str, str] | None = None,
  call_api: SchedulerCall | None = None,
) -> dict[str, Any]:
  return _toggle_scheduler_state("pause", environ=environ, call_api=call_api)


def resume_scheduler_job(
  *,
  environ: Mapping[str, str] | None = None,
  call_api: SchedulerCall | None = None,
) -> dict[str, Any]:
  return _toggle_scheduler_state("resume", environ=environ, call_api=call_api)


def _toggle_scheduler_state(
  action: str,
  *,
  environ: Mapping[str, str] | None = None,
  call_api: SchedulerCall | None = None,
) -> dict[str, Any]:
  assert_external_execution_allowed("cloud_scheduler")
  if not is_cloud_scheduler_admin_enabled(environ):
    return _blocked_response("クラウド管理機能が無効です。")
  project = get_google_cloud_project(environ)
  region = get_scheduler_region(environ)
  job_name = get_scheduler_job_name(environ)
  if not project or not region or not job_name:
    return _blocked_response("Scheduler操作に必要な project / region / job name が未設定です。")
  payload = _call_scheduler_api("POST", _job_url(project, region, job_name) + f":{action}", {}, call_api=call_api)
  return {
    "status": "success",
    "job_name": job_name,
    "state": str(payload.get("state", "PAUSED" if action == "pause" else "ENABLED") or ""),
    "payload": payload,
    "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
  }


def _job_url(project: str, region: str, job_name: str) -> str:
  return f"https://cloudscheduler.googleapis.com/v1/projects/{project}/locations/{region}/jobs/{job_name}"


def _call_scheduler_api(
  method: str,
  url: str,
  body: dict[str, Any] | None,
  *,
  call_api: SchedulerCall | None,
) -> dict[str, Any]:
  if call_api is not None:
    return dict(call_api(method, url, body) or {})
  session = _build_authorized_session()
  request = urllib.request.Request(
    url,
    data=None if body is None else json.dumps(body).encode("utf-8"),
    headers={"Content-Type": "application/json; charset=utf-8"},
    method=method,
  )
  try:
    response = session.open(request)
  except urllib.error.HTTPError as exc:  # noqa: PERF203
    message = exc.read().decode("utf-8", errors="replace")
    raise RuntimeError(f"Scheduler API request failed: {exc.code} {message}") from exc
  return json.loads(response.read().decode("utf-8"))


def _build_authorized_session():
  import google.auth.transport.requests
  from google.auth import default

  credentials, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
  credentials.refresh(google.auth.transport.requests.Request())
  opener = urllib.request.build_opener()
  opener.addheaders = [("Authorization", f"Bearer {credentials.token}")]
  return opener


def _blocked_response(message: str) -> dict[str, Any]:
  return {
    "status": "blocked",
    "message": message,
    "payload": {},
  }


__all__ = [
  "apply_scheduler_settings",
  "get_scheduler_job_status",
  "pause_scheduler_job",
  "resume_scheduler_job",
]
