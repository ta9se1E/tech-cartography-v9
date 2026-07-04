"""Tests for v9 Cloud Scheduler admin helpers."""

from __future__ import annotations

from services_v9.cloud_scheduler_admin import (
  apply_scheduler_settings,
  get_scheduler_job_status,
  pause_scheduler_job,
  resume_scheduler_job,
)


def _env(enabled: bool = True) -> dict[str, str]:
  return {
    "V9_ENABLE_CLOUD_SCHEDULER_ADMIN": "true" if enabled else "false",
    "GOOGLE_CLOUD_PROJECT": "demo-project",
    "V9_SCHEDULER_REGION": "us-central1",
    "V9_SCHEDULER_JOB_NAME": "v9-weekly-job",
  }


def test_get_scheduler_job_status_is_blocked_when_admin_disabled() -> None:
  result = get_scheduler_job_status(environ=_env(enabled=False))
  assert result["status"] == "blocked"


def test_get_scheduler_job_status_uses_fixed_job_url() -> None:
  calls: list[tuple[str, str, dict | None]] = []

  def fake_call(method: str, url: str, body):
    calls.append((method, url, body))
    return {"schedule": "0 9 * * 1", "timeZone": "Asia/Tokyo", "state": "PAUSED"}

  result = get_scheduler_job_status(environ=_env(), call_api=fake_call)
  assert result["status"] == "success"
  assert calls == [("GET", "https://cloudscheduler.googleapis.com/v1/projects/demo-project/locations/us-central1/jobs/v9-weekly-job", None)]


def test_apply_scheduler_settings_updates_schedule_and_pauses_when_disabled() -> None:
  calls: list[tuple[str, str, dict | None]] = []

  def fake_call(method: str, url: str, body):
    calls.append((method, url, body))
    if method == "PATCH":
      return {"schedule": body["schedule"], "timeZone": body["timeZone"]}
    return {"state": "PAUSED"}

  result = apply_scheduler_settings(
    {
      "enabled": False,
      "cron_expression": "30 8 * * 1",
      "timezone": "Asia/Tokyo",
    },
    environ=_env(),
    call_api=fake_call,
  )
  assert result["status"] == "success"
  assert calls[0][0] == "PATCH"
  assert "updateMask=schedule,timeZone" in calls[0][1]
  assert calls[1][1].endswith(":pause")


def test_resume_and_pause_scheduler_job_use_fixed_endpoints() -> None:
  calls: list[str] = []

  def fake_call(method: str, url: str, body):
    calls.append(url)
    return {"state": "ENABLED" if url.endswith(":resume") else "PAUSED"}

  resume_result = resume_scheduler_job(environ=_env(), call_api=fake_call)
  pause_result = pause_scheduler_job(environ=_env(), call_api=fake_call)
  assert resume_result["state"] == "ENABLED"
  assert pause_result["state"] == "PAUSED"
  assert calls[0].endswith(":resume")
  assert calls[1].endswith(":pause")
