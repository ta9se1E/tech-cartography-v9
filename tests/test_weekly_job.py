"""Tests for weekly digest job (Phase 24.3)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from tech_cartography.delivery.send_log import STATUS_SENT, save_send_log, EmailSendLog
from tech_cartography.delivery.weekly_job import (
  JOB_STATUS_BLOCKED,
  JOB_STATUS_DRAFT_SAVED,
  JOB_STATUS_DRY_RUN,
  JOB_STATUS_SENT,
  JOB_STATUS_SKIPPED,
  WeeklyJobConfig,
  build_weekly_job_config,
  run_weekly_digest_job,
  save_weekly_job_log,
  should_skip_already_sent_this_week,
)

from tests.test_digest_diff import _write_snapshot_fixture


def test_build_weekly_job_config() -> None:
  config = build_weekly_job_config(
    publication_number="US-12565719-B2",
    recipient_config_path="config/email_recipients.json",
    recipient_group="internal_review",
  )
  assert config.publication_number == "US-12565719-B2"
  assert config.build_draft is True
  assert config.send_email is False
  assert config.timezone == "Asia/Tokyo"


def test_should_skip_when_sent_this_week(tmp_path: Path) -> None:
  out = tmp_path / "outputs" / "delivery"
  tz = ZoneInfo("Asia/Tokyo")
  now = datetime.now(tz).isoformat()
  save_send_log(
    EmailSendLog(
      log_id="log-sent",
      created_at=now,
      publication_number="US-12565719-B2",
      subject="Test",
      to_count=1,
      cc_count=0,
      status=STATUS_SENT,
      message="sent",
    ),
    out,
  )
  skip, reason = should_skip_already_sent_this_week("US-12565719-B2", out)
  assert skip is True
  assert "今週" in reason


def test_allow_repeat_skips_check_via_config(tmp_path: Path, monkeypatch) -> None:
  _write_snapshot_fixture(tmp_path)
  out = tmp_path / "outputs" / "delivery"
  tz = ZoneInfo("Asia/Tokyo")
  save_send_log(
    EmailSendLog(
      log_id="log-sent",
      created_at=datetime.now(tz).isoformat(),
      publication_number="US-12565719-B2",
      subject="Test",
      to_count=1,
      cc_count=0,
      status=STATUS_SENT,
      message="sent",
    ),
    out,
  )
  config = build_weekly_job_config(
    publication_number="US-12565719-B2",
    recipient_config_path=tmp_path / "recipients.json",
    recipient_group="default",
    output_dir=out,
    project_root=tmp_path,
    send_email=True,
    allow_repeat_this_week=True,
  )
  (tmp_path / "recipients.json").write_text(
    json.dumps({"default": {"to": ["a@example.com"], "cc": [], "enabled": True}}),
    encoding="utf-8",
  )
  with patch("tech_cartography.delivery.weekly_job.run_weekly_digest_send_test") as mock_send:
    mock_send.return_value = type(
      "R",
      (),
      {
        "delivery_paths": {},
        "send_log": EmailSendLog(
          log_id="x",
          created_at="2026-06-20T00:00:00+00:00",
          publication_number="US-12565719-B2",
          subject="s",
          to_count=1,
          cc_count=0,
          status=STATUS_SENT,
          message="sent",
        ),
        "send_log_paths": {"send_log_latest": out / "email_send_logs" / "send_log_latest_US-12565719-B2.json"},
      },
    )()
    result = run_weekly_digest_job(config)
  assert result.status != JOB_STATUS_SKIPPED
  mock_send.assert_called_once()


def test_run_job_dry_run(tmp_path: Path) -> None:
  _write_snapshot_fixture(tmp_path)
  config_path = tmp_path / "recipients.json"
  config_path.write_text(
    json.dumps({"default": {"to": ["a@example.com"], "cc": [], "enabled": True}}),
    encoding="utf-8",
  )
  out = tmp_path / "outputs" / "delivery"
  config = build_weekly_job_config(
    publication_number="US-12565719-B2",
    recipient_config_path=config_path,
    output_dir=out,
    project_root=tmp_path,
    dry_run=True,
    send_email=True,
  )
  result = run_weekly_digest_job(config)
  assert result.status == JOB_STATUS_DRY_RUN
  assert (out / "job_logs" / "job_log_latest_US-12565719-B2.json").exists()


def test_run_job_draft_only_no_send(tmp_path: Path) -> None:
  _write_snapshot_fixture(tmp_path)
  config_path = tmp_path / "recipients.json"
  config_path.write_text(
    json.dumps({"default": {"to": ["a@example.com"], "cc": [], "enabled": True}}),
    encoding="utf-8",
  )
  out = tmp_path / "outputs" / "delivery"
  with patch("tech_cartography.delivery.weekly_job.run_weekly_digest_send_test") as mock_send:
    mock_send.return_value = type(
      "R",
      (),
      {
        "delivery_paths": {"email_draft_md": str(out / "email_outbox" / "email_draft_US-12565719-B2.md")},
        "send_log": EmailSendLog(
          log_id="x",
          created_at="2026-06-20T00:00:00+00:00",
          publication_number="US-12565719-B2",
          subject="s",
          to_count=1,
          cc_count=0,
          status="draft_saved",
          message="draft",
          draft_path=str(out / "email_outbox" / "email_draft_US-12565719-B2.md"),
        ),
        "send_log_paths": {"send_log_latest": out / "email_send_logs" / "send_log_latest_US-12565719-B2.json"},
      },
    )()
    config = build_weekly_job_config(
      publication_number="US-12565719-B2",
      recipient_config_path=config_path,
      output_dir=out,
      project_root=tmp_path,
      send_email=False,
      build_draft=True,
    )
    result = run_weekly_digest_job(config)
  assert result.status == JOB_STATUS_DRAFT_SAVED
  called = mock_send.call_args.kwargs
  assert called["send_email"] is False


def test_run_job_skip_already_sent(tmp_path: Path) -> None:
  out = tmp_path / "outputs" / "delivery"
  tz = ZoneInfo("Asia/Tokyo")
  save_send_log(
    EmailSendLog(
      log_id="log-sent",
      created_at=datetime.now(tz).isoformat(),
      publication_number="US-12565719-B2",
      subject="Test",
      to_count=1,
      cc_count=0,
      status=STATUS_SENT,
      message="sent",
    ),
    out,
  )
  config = WeeklyJobConfig(
    publication_number="US-12565719-B2",
    recipient_config_path="config/email_recipients.json",
    output_dir=str(out),
    project_root=str(tmp_path),
    send_email=True,
    allow_repeat_this_week=False,
  )
  result = run_weekly_digest_job(config)
  assert result.status == JOB_STATUS_SKIPPED


def test_run_job_blocked_when_smtp_missing(tmp_path: Path, monkeypatch) -> None:
  for key in (
    "TC_SMTP_HOST", "TC_SMTP_PORT", "TC_SMTP_USER", "TC_SMTP_PASSWORD", "TC_SMTP_FROM",
    "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "SMTP_FROM_EMAIL",
  ):
    monkeypatch.delenv(key, raising=False)
  _write_snapshot_fixture(tmp_path)
  config_path = tmp_path / "recipients.json"
  config_path.write_text(
    json.dumps({"default": {"to": ["a@example.com"], "cc": [], "enabled": True}}),
    encoding="utf-8",
  )
  out = tmp_path / "outputs" / "delivery"
  config = build_weekly_job_config(
    publication_number="US-12565719-B2",
    recipient_config_path=config_path,
    output_dir=out,
    project_root=tmp_path,
    send_email=True,
    allow_repeat_this_week=True,
  )
  result = run_weekly_digest_job(config)
  assert result.status == JOB_STATUS_BLOCKED


def test_save_weekly_job_log(tmp_path: Path) -> None:
  from tech_cartography.delivery.weekly_job import WeeklyJobResult

  out = tmp_path / "outputs" / "delivery"
  result = WeeklyJobResult(
    job_id="job-1",
    created_at="2026-06-20T00:00:00+00:00",
    publication_number="US-1",
    status=JOB_STATUS_DRAFT_SAVED,
    message="ok",
  )
  paths = save_weekly_job_log(result, out)
  assert paths["job_log_latest"].exists()
  assert result.job_log_path is not None
