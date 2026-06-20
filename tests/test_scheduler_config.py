"""Tests for scheduler config (Phase 24.3)."""

from __future__ import annotations

import plistlib
import sys
from pathlib import Path

from tech_cartography.delivery.scheduler_config import (
  SchedulerConfig,
  build_cron_line,
  build_launchd_plist,
  build_scheduler_wrapper_script,
  render_scheduler_readme,
  save_scheduler_bundle,
)


def _sample_config(tmp_path: Path, *, enable_send: bool = False) -> SchedulerConfig:
  return SchedulerConfig(
    project_dir=tmp_path,
    python_bin=Path(sys.executable),
    publication_number="US-12565719-B2",
    recipient_config="config/email_recipients.json",
    recipient_group="internal_review",
    output_dir="outputs/delivery",
    weekday=1,
    hour=8,
    minute=30,
    timezone="Asia/Tokyo",
    enable_send=enable_send,
    label="com.techcartography.weeklydigest",
    allow_repeat_this_week=False,
  )


def test_wrapper_script_sources_env(tmp_path: Path) -> None:
  config = _sample_config(tmp_path)
  script = build_scheduler_wrapper_script(config)
  assert 'source ".env"' in script
  assert "SMTP_PASSWORD" not in script
  assert "--build-draft" in script
  assert "--send-email" not in script


def test_wrapper_script_includes_send_when_enabled(tmp_path: Path) -> None:
  config = _sample_config(tmp_path, enable_send=True)
  script = build_scheduler_wrapper_script(config)
  assert "--send-email" in script


def test_launchd_plist_no_send_by_default(tmp_path: Path) -> None:
  config = _sample_config(tmp_path)
  wrapper = tmp_path / "outputs" / "delivery" / "scheduler" / "run_weekly_digest_job.sh"
  wrapper.parent.mkdir(parents=True, exist_ok=True)
  wrapper.write_text(build_scheduler_wrapper_script(config), encoding="utf-8")
  plist = build_launchd_plist(config, wrapper)
  assert plist["Label"] == "com.techcartography.weeklydigest"
  assert plist["ProgramArguments"][0] == "/bin/bash"
  assert "--send-email" not in build_scheduler_wrapper_script(config)


def test_cron_sample_generated(tmp_path: Path) -> None:
  config = _sample_config(tmp_path)
  line = build_cron_line(config)
  assert "30 8 * * 1" in line
  assert "source .env" in line
  assert "--send-email" not in line


def test_cron_sample_with_send(tmp_path: Path) -> None:
  config = _sample_config(tmp_path, enable_send=True)
  line = build_cron_line(config)
  assert "--send-email" in line


def test_save_scheduler_bundle(tmp_path: Path) -> None:
  config = _sample_config(tmp_path)
  paths = save_scheduler_bundle(config)
  assert paths["wrapper_script"].exists()
  assert paths["launchd_plist"].exists()
  assert paths["cron_sample"].exists()
  assert paths["scheduler_readme"].exists()
  assert oct(paths["wrapper_script"].stat().st_mode & 0o111) != "0o0"

  with paths["launchd_plist"].open("rb") as handle:
    data = plistlib.load(handle)
  assert data["StartCalendarInterval"]["Weekday"] == 1
  assert data["StartCalendarInterval"]["Hour"] == 8


def test_scheduler_readme_content(tmp_path: Path) -> None:
  config = _sample_config(tmp_path)
  paths = save_scheduler_bundle(config)
  text = render_scheduler_readme(config, paths)
  assert "wrapper script" in text or "wrapper" in text
  assert "UIから" in text
