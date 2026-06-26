"""Tests for check_v8_reframe_ready.py (Phase27A)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts/check_v8_reframe_ready.py"


def _load_module():
  spec = importlib.util.spec_from_file_location("check_v8_reframe_ready_mod", SCRIPT)
  assert spec and spec.loader
  module = importlib.util.module_from_spec(spec)
  sys.modules[spec.name] = module
  spec.loader.exec_module(module)
  return module


def test_check_v8_reframe_ready_script_exists() -> None:
  assert SCRIPT.exists()
  text = SCRIPT.read_text(encoding="utf-8")
  assert "v8 reframe readiness" in text
  assert "case_01_pan_graphitization" in text


def test_check_v8_reframe_ready_passes(capsys: pytest.CaptureFixture[str]) -> None:
  module = _load_module()
  code = module.main()
  out = capsys.readouterr().out
  assert code == 0
  assert "v8 reframe readiness: PASS" in out
  assert "PASS: artifact exists: docs/v8_product_reframe.md" in out


def test_check_v8_reframe_ready_subprocess() -> None:
  result = subprocess.run(
    [sys.executable, str(SCRIPT)],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0
  assert "PASS" in result.stdout
