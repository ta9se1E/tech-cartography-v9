"""Tests for v8 large candidate scripts (Phase 27J.0)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMPORT_SCRIPT = PROJECT_ROOT / "scripts" / "run_v8_large_candidate_import.py"
SHORTLIST_SCRIPT = PROJECT_ROOT / "scripts" / "run_v8_large_candidate_shortlist.py"
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "v8_large_candidate_fixture.csv"


def test_import_script_importable() -> None:
  spec = importlib.util.spec_from_file_location("run_v8_large_candidate_import", IMPORT_SCRIPT)
  assert spec and spec.loader
  module = importlib.util.module_from_spec(spec)
  sys.path.insert(0, str(PROJECT_ROOT / "src"))
  spec.loader.exec_module(module)
  assert callable(module.main)


def test_shortlist_script_after_import(tmp_path: Path) -> None:
  env = {**dict(__import__("os").environ), "PYTHONPATH": str(PROJECT_ROOT / "src")}
  proc1 = subprocess.run(
    [
      sys.executable, str(IMPORT_SCRIPT),
      "--case-id", "case_01_pan_graphitization",
      "--input", str(FIXTURE),
      "--max-rows", "100",
    ],
    cwd=PROJECT_ROOT,
    env=env,
    capture_output=True,
    text=True,
    timeout=60,
  )
  assert proc1.returncode == 0
  proc2 = subprocess.run(
    [sys.executable, str(SHORTLIST_SCRIPT), "--case-id", "case_01_pan_graphitization"],
    cwd=PROJECT_ROOT,
    env=env,
    capture_output=True,
    text=True,
    timeout=60,
  )
  assert "top5 count:" in proc2.stdout
  for pattern in ("source_candidates_large.csv", "source_candidates_large_profile.json"):
    p = PROJECT_ROOT / "cases" / "case_01_pan_graphitization" / pattern
    if p.exists():
      p.unlink()
