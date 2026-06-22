"""Tests for check_cicd_ready.py (Phase 25P)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts/check_cicd_ready.py"


def _load_module():
  spec = importlib.util.spec_from_file_location("check_cicd_ready_mod", SCRIPT)
  assert spec and spec.loader
  module = importlib.util.module_from_spec(spec)
  sys.modules[spec.name] = module
  spec.loader.exec_module(module)
  return module


def test_check_cicd_ready_skip_gcloud(capsys: pytest.CaptureFixture[str]) -> None:
  module = _load_module()
  code = module.main(["--skip-gcloud"])
  out = capsys.readouterr().out
  assert code == 0
  assert "PASS: artifact exists: cloudbuild.yaml" in out
  assert "CI/CD readiness:" in out
  for forbidden in ("sk-", "eyJhbGci", "smtp-pass", "test-password"):
    assert forbidden not in out.lower()


def test_check_cicd_ready_script_has_readiness_banner() -> None:
  text = SCRIPT.read_text(encoding="utf-8")
  assert "CI/CD readiness" in text
  assert "cloudbuild.yaml" in text
