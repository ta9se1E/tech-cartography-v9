"""Tests for v8 manual claim refresh script (Phase 27J)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "run_v8_manual_claim_refresh.py"


def test_manual_claim_refresh_script_importable() -> None:
  spec = importlib.util.spec_from_file_location("run_v8_manual_claim_refresh", SCRIPT)
  assert spec and spec.loader
  module = importlib.util.module_from_spec(spec)
  sys.path.insert(0, str(PROJECT_ROOT / "src"))
  spec.loader.exec_module(module)
  assert callable(module.main)


def test_script_stops_without_claim_text() -> None:
  env = {**dict(__import__("os").environ), "PYTHONPATH": str(PROJECT_ROOT / "src")}
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--case-id",
      "case_01_pan_graphitization",
      "--publication-number",
      "US5176959",
      "--claim-no",
      "1",
    ],
    cwd=PROJECT_ROOT,
    env=env,
    capture_output=True,
    text=True,
    timeout=60,
  )
  assert proc.returncode == 1
  assert "claim 本文がありません" in proc.stderr or "claim 本文がありません" in proc.stdout
