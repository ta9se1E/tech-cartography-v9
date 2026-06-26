"""Tests for run_v8_demo_readiness_check script (Phase 27M)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "run_v8_demo_readiness_check.py"


def test_script_importable() -> None:
  spec = importlib.util.spec_from_file_location("run_v8_demo_readiness_check", SCRIPT)
  assert spec and spec.loader
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  assert hasattr(module, "main")
