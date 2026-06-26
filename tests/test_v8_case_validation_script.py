"""Tests for v8 three case validation script (Phase 27I)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "run_v8_three_case_validation_pack.py"


def test_validation_script_importable() -> None:
  spec = importlib.util.spec_from_file_location("run_v8_three_case_validation_pack", SCRIPT)
  assert spec and spec.loader
  module = importlib.util.module_from_spec(spec)
  sys.path.insert(0, str(PROJECT_ROOT / "src"))
  spec.loader.exec_module(module)
  assert callable(module.main)


def test_validation_script_main_runs() -> None:
  env = {**dict(__import__("os").environ), "PYTHONPATH": str(PROJECT_ROOT / "src")}
  proc = subprocess.run(
    [sys.executable, str(SCRIPT)],
    cwd=PROJECT_ROOT,
    env=env,
    capture_output=True,
    text=True,
    timeout=180,
  )
  assert "overall_status:" in proc.stdout
  assert "readiness_for_demo=" in proc.stdout
  assert "manifest:" in proc.stdout
  assert proc.returncode in {0, 1}
