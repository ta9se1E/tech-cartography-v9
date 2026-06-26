"""Tests for v8 One Case Demo E2E script (Phase 27N.5)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "run_v8_one_case_demo_e2e_check.py"
DEFAULT_CSV = (
  PROJECT_ROOT
  / "cases/case_01_pan_graphitization/large_candidates/case_01_bigquery_export_1000.csv"
)


def test_script_importable() -> None:
  spec = importlib.util.spec_from_file_location("run_v8_one_case_demo_e2e_check", SCRIPT)
  assert spec and spec.loader
  mod = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(mod)
  assert hasattr(mod, "main")


def test_missing_csv_exits_with_guidance() -> None:
  if DEFAULT_CSV.is_file():
    return
  proc = subprocess.run(
    [sys.executable, str(SCRIPT)],
    cwd=str(PROJECT_ROOT),
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 1
  assert "input_csv_exists: false" in proc.stdout
  assert "case_01_bigquery_export_1000.csv" in proc.stdout
  assert "fixture" in proc.stdout.lower() or "架空" in proc.stdout


def test_assess_does_not_generate_claim() -> None:
  from tech_cartography.services.v8_one_case_demo_e2e import assess_one_case_demo_status

  summary = assess_one_case_demo_status(project_root=PROJECT_ROOT)
  assert summary.no_claim_text_generated is True
