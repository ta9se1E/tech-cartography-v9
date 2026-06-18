"""Tests for build_strategic_watch_brief CLI (Phase 23.5)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.test_strategic_watch_brief import _write_fixture

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "build_strategic_watch_brief.py"


def test_cli_dry_run_subprocess() -> None:
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--publication-number",
      "US-12565719-B2",
      "--dry-run",
    ],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0
  payload = json.loads(proc.stdout)
  assert payload["publication_number"] == "US-12565719-B2"


def test_cli_build_with_fixture(tmp_path: Path) -> None:
  _write_fixture(tmp_path)
  out_dir = tmp_path / "outputs/strategic_watch_briefs/US-12565719-B2"
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--publication-number",
      "US-12565719-B2",
      "--web-signal-link-dir",
      str(tmp_path / "outputs/web_signal_links/US-12565719-B2"),
      "--output-dir",
      str(out_dir),
    ],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0, proc.stderr
  assert (out_dir / "strategic_watch_items.csv").exists()


def test_cli_missing_inputs_no_crash() -> None:
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--publication-number",
      "US-MISSING-PATENT",
      "--dry-run",
    ],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0
