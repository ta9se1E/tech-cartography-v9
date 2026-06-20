"""Tests for send_weekly_digest_test CLI (Phase 24.2)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from tech_cartography.delivery.send_log import STATUS_DRY_RUN, STATUS_BLOCKED_RECIPIENT_DISABLED
from tech_cartography.delivery.weekly_digest_send import run_weekly_digest_send_test

from tests.test_digest_diff import _write_snapshot_fixture

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "send_weekly_digest_test.py"
EXAMPLE_CONFIG = PROJECT_ROOT / "config" / "email_recipients.example.json"


def test_dry_run_does_not_send(tmp_path: Path) -> None:
  _write_snapshot_fixture(tmp_path)
  out = tmp_path / "outputs" / "delivery"
  result = run_weekly_digest_send_test(
    publication_number="US-12565719-B2",
    project_root=tmp_path,
    output_dir=out,
    recipient_config_path=EXAMPLE_CONFIG,
    recipient_group="default",
    dry_run=True,
  )
  assert result.send_log is not None
  assert result.send_log.status == STATUS_BLOCKED_RECIPIENT_DISABLED
  assert result.send_log_paths


def test_build_draft_without_send_email(tmp_path: Path) -> None:
  _write_snapshot_fixture(tmp_path)
  config = tmp_path / "recipients.json"
  config.write_text(
    json.dumps(
      {
        "default": {
          "to": ["reviewer@example.com"],
          "cc": [],
          "enabled": True,
        },
      },
    ),
    encoding="utf-8",
  )
  out = tmp_path / "outputs" / "delivery"
  with patch("tech_cartography.delivery.weekly_digest_send.send_email_smtp") as mock_send:
    result = run_weekly_digest_send_test(
      publication_number="US-12565719-B2",
      project_root=tmp_path,
      output_dir=out,
      recipient_config_path=config,
      recipient_group="default",
      build_draft=True,
      send_email=False,
    )
    mock_send.assert_not_called()
  assert result.send_log is not None
  assert (out / "email_outbox" / "email_draft_US-12565719-B2.json").exists()
  assert (out / "email_send_logs" / "send_log_latest_US-12565719-B2.json").exists()


def test_send_email_without_flag_does_not_call_smtp(tmp_path: Path) -> None:
  _write_snapshot_fixture(tmp_path)
  config = tmp_path / "recipients.json"
  config.write_text(
    json.dumps({"default": {"to": ["reviewer@example.com"], "cc": [], "enabled": True}}),
    encoding="utf-8",
  )
  out = tmp_path / "outputs" / "delivery"
  with patch("tech_cartography.delivery.weekly_digest_send.send_email_smtp") as mock_send:
    run_weekly_digest_send_test(
      publication_number="US-12565719-B2",
      project_root=tmp_path,
      output_dir=out,
      recipient_config_path=config,
      recipient_group="default",
      build_draft=True,
      send_email=False,
    )
    mock_send.assert_not_called()


def test_send_email_smtp_missing_blocked(tmp_path: Path, monkeypatch) -> None:
  for key in ("TC_SMTP_HOST", "TC_SMTP_PORT", "TC_SMTP_USER", "TC_SMTP_PASSWORD", "TC_SMTP_FROM"):
    monkeypatch.delenv(key, raising=False)
  _write_snapshot_fixture(tmp_path)
  config = tmp_path / "recipients.json"
  config.write_text(
    json.dumps({"default": {"to": ["reviewer@example.com"], "cc": [], "enabled": True}}),
    encoding="utf-8",
  )
  out = tmp_path / "outputs" / "delivery"
  result = run_weekly_digest_send_test(
    publication_number="US-12565719-B2",
    project_root=tmp_path,
    output_dir=out,
    recipient_config_path=config,
    recipient_group="default",
    build_draft=True,
    send_email=True,
  )
  assert result.send_log is not None
  assert result.send_log.status == "blocked_missing_adapter"


def test_cli_dry_run_subprocess() -> None:
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--publication-number",
      "US-12565719-B2",
      "--recipient-config",
      "config/email_recipients.example.json",
      "--recipient-group",
      "default",
      "--dry-run",
    ],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0
  payload = json.loads(proc.stdout)
  assert payload["dry_run"] is True
  assert "send_log" in payload
