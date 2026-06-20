"""Tests for run_weekly_digest_job CLI (Phase 24.3)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.test_digest_diff import _write_snapshot_fixture

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "run_weekly_digest_job.py"


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
  assert payload["status"] in {"dry_run", "blocked"}


def test_cli_build_draft_subprocess(tmp_path: Path) -> None:
  _write_snapshot_fixture(tmp_path)
  config = tmp_path / "recipients.json"
  config.write_text(
    json.dumps({"default": {"to": ["reviewer@example.com"], "cc": [], "enabled": True}}),
    encoding="utf-8",
  )
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--publication-number",
      "US-12565719-B2",
      "--recipient-config",
      str(config),
      "--recipient-group",
      "default",
      "--output-dir",
      str(tmp_path / "outputs" / "delivery"),
      "--project-root",
      str(tmp_path),
      "--build-draft",
      "--no-include-zip",
    ],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0
  payload = json.loads(proc.stdout)
  assert payload["status"] in {"draft_saved", "blocked"}
