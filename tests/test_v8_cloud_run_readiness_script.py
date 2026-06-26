"""Tests for v8 Cloud Run readiness script (Phase 27N)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "run_v8_cloud_run_readiness_check.py"


def test_script_importable() -> None:
  spec = importlib.util.spec_from_file_location("run_v8_cloud_run_readiness_check", SCRIPT)
  assert spec and spec.loader
  mod = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(mod)
  assert hasattr(mod, "main")


def test_script_main_runs() -> None:
  proc = subprocess.run(
    [sys.executable, str(SCRIPT)],
    cwd=str(PROJECT_ROOT),
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0
  assert "overall_status:" in proc.stdout
  assert "Cloud Build executed: false" in proc.stdout
  assert "Cloud Run deploy executed: false" in proc.stdout
