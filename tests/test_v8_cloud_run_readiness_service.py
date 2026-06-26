"""Tests for v8 Cloud Run readiness service (Phase 27N)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tech_cartography.services.v8_cloud_run_readiness import (
  RECOMMENDED_STREAMLIT_CMD,
  build_cloud_run_readiness_report,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_build_report_json_serializable() -> None:
  report = build_cloud_run_readiness_report(project_root=PROJECT_ROOT)
  blob = json.dumps(report.to_dict())
  parsed = json.loads(blob)
  assert parsed["no_cloud_build_executed"] is True
  assert parsed["no_cloud_run_deploy_executed"] is True


def test_app_entrypoint_pass() -> None:
  report = build_cloud_run_readiness_report(project_root=PROJECT_ROOT)
  assert report.app_entrypoint_status in {"pass", "warning"}


def test_port_aware_command_documented() -> None:
  procfile = (PROJECT_ROOT / "Procfile").read_text(encoding="utf-8")
  dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
  docs = (PROJECT_ROOT / "docs" / "cloud_run_v8_prepare.md").read_text(encoding="utf-8")
  combined = procfile + dockerfile + docs
  assert "${PORT" in combined or "$PORT" in combined
  assert "streamlit run app.py" in combined


def test_demo_data_not_deploy_blocker() -> None:
  report = build_cloud_run_readiness_report(project_root=PROJECT_ROOT)
  demo_check = next(c for c in report.check_results if c.check_id == "demo_data")
  assert "技術ブロッカー" in demo_check.summary or "not_ready" in demo_check.summary.lower()
  deploy_blockers = [b for b in report.known_blockers if "demo" in b.lower()]
  assert not deploy_blockers


def test_recommended_streamlit_cmd_has_port() -> None:
  assert "${PORT" in RECOMMENDED_STREAMLIT_CMD or "$PORT" in RECOMMENDED_STREAMLIT_CMD


def test_artifact_policy_tmp_or_cloud_storage() -> None:
  report = build_cloud_run_readiness_report(project_root=PROJECT_ROOT)
  assert report.artifact_policy is not None
  assert "/tmp" in report.artifact_policy.cloud_output_root
  assert report.artifact_policy.recommended_storage_option in {
    "local_tmp",
    "cloud_storage_later",
    "not_required_for_demo",
  }
