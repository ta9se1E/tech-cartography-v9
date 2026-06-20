"""Tests for install_weekly_digest_schedule CLI (Phase 24.3)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from tech_cartography.delivery.scheduler_config import SchedulerConfig, save_scheduler_bundle

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "install_weekly_digest_schedule.py"


def test_install_generates_files_without_launchctl(tmp_path: Path) -> None:
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--publication-number",
      "US-12565719-B2",
      "--recipient-config",
      "config/email_recipients.json",
      "--recipient-group",
      "internal_review",
      "--project-dir",
      str(tmp_path),
      "--output-dir",
      str(tmp_path / "outputs" / "delivery"),
      "--python-bin",
      sys.executable,
    ],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0
  payload = json.loads(proc.stdout)
  sched = tmp_path / "outputs" / "delivery" / "scheduler"
  assert (sched / "run_weekly_digest_job.sh").exists()
  assert (sched / "com.techcartography.weeklydigest.plist").exists()
  assert "launchctl not run" in payload["install_message"]


def test_install_only_without_yes_does_not_launchctl(tmp_path: Path) -> None:
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--publication-number",
      "US-12565719-B2",
      "--recipient-config",
      "config/email_recipients.json",
      "--project-dir",
      str(tmp_path),
      "--output-dir",
      str(tmp_path / "outputs" / "delivery"),
      "--install",
    ],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0
  payload = json.loads(proc.stdout)
  assert payload["install_requested"] is True
  assert payload["yes"] is False
  assert "yes" in payload["install_message"].lower()
  assert payload.get("install_ok") is not True


def test_install_launchd_agent_function(tmp_path: Path) -> None:
  from scripts.install_weekly_digest_schedule import install_launchd_agent

  config = SchedulerConfig(
    project_dir=tmp_path,
    python_bin=Path(sys.executable),
    publication_number="US-12565719-B2",
    recipient_config="config/email_recipients.json",
    recipient_group="default",
    output_dir=str(tmp_path / "outputs" / "delivery"),
    weekday=1,
    hour=8,
    minute=30,
    timezone="Asia/Tokyo",
    enable_send=False,
    label="com.techcartography.weeklydigest",
    allow_repeat_this_week=False,
  )
  paths = save_scheduler_bundle(config)
  agents_dir = tmp_path / "LaunchAgents"
  agents_dir.mkdir(parents=True, exist_ok=True)
  with (
    patch("scripts.install_weekly_digest_schedule.Path.home", return_value=tmp_path),
    patch("scripts.install_weekly_digest_schedule.subprocess.run") as mock_run,
  ):
    mock_run.return_value = type("R", (), {"returncode": 0, "stderr": "", "stdout": "ok"})()
    ok, message = install_launchd_agent(paths["launchd_plist"], config.label)
  assert ok is True
  assert mock_run.call_count >= 1
  assert "load" in message


def test_enable_send_wrapper_contains_send_flag(tmp_path: Path) -> None:
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--publication-number",
      "US-12565719-B2",
      "--recipient-config",
      "config/email_recipients.json",
      "--project-dir",
      str(tmp_path),
      "--output-dir",
      str(tmp_path / "outputs" / "delivery"),
      "--enable-send",
    ],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0
  wrapper = (tmp_path / "outputs" / "delivery" / "scheduler" / "run_weekly_digest_job.sh").read_text(
    encoding="utf-8",
  )
  assert "--send-email" in wrapper
  assert "SMTP_PASSWORD" not in wrapper
