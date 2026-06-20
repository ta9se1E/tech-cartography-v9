"""Tests for run_theme_validation_smoke CLI (Phase 24.4)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "run_theme_validation_smoke.py"
EXAMPLE_CONFIG = PROJECT_ROOT / "config" / "theme_validation_cases.example.json"


def test_cli_dry_run_example_theme() -> None:
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--theme-config",
      str(EXAMPLE_CONFIG),
      "--theme-id",
      "pan_carbon_fiber_reference",
      "--dry-run",
    ],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0
  payload = json.loads(proc.stdout)
  assert payload["theme_id"] == "pan_carbon_fiber_reference"
  assert payload["no_external_api"] is True
  assert payload["dry_run"] is True
  assert len(payload["stages"]) >= 1


def test_cli_theme_not_found() -> None:
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--theme-config",
      str(EXAMPLE_CONFIG),
      "--theme-id",
      "missing_theme",
    ],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 1
