"""Tests for v8 demo readiness service (Phase 27M)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tech_cartography.services.v8_demo_readiness import (
  assess_case_demo_readiness,
  build_demo_readiness_report,
)
from tech_cartography.services.v8_sources_table import project_root_from_here

CASE_ID = "case_01_pan_graphitization"


@pytest.fixture
def case_root(tmp_path: Path) -> Path:
  root = project_root_from_here()
  case_dst = tmp_path / "cases" / CASE_ID
  case_dst.mkdir(parents=True)
  for name in ("claims_input.csv", "source_candidates.csv", "case_profile.yaml"):
    src = root / "cases" / CASE_ID / name
    if src.exists():
      shutil.copy(src, case_dst / name)
  return tmp_path


def test_assess_distinguishes_missing_evidence_artifact(case_root: Path) -> None:
  readiness = assess_case_demo_readiness(CASE_ID, project_root=case_root)
  ev_step = next(s for s in readiness.step_statuses if s.step_name == "evidence_map")
  if not ev_step.primary_artifact_exists:
    assert ev_step.status == "not_generated"
    assert readiness.evidence_link_count is None
    assert ev_step.key_counts.get("evidence_link_count") == "artifact_missing"


def test_assess_distinguishes_missing_gap_artifact(case_root: Path) -> None:
  readiness = assess_case_demo_readiness(CASE_ID, project_root=case_root)
  gap_step = next(s for s in readiness.step_statuses if s.step_name == "gap_next_actions")
  if not gap_step.primary_artifact_exists:
    assert gap_step.status == "not_generated"
    assert readiness.gap_count is None


def test_next_user_action_present(case_root: Path) -> None:
  readiness = assess_case_demo_readiness(CASE_ID, project_root=case_root)
  assert readiness.next_3_user_actions
  assert readiness.recommended_demo_flow


def test_build_three_case_report(case_root: Path) -> None:
  report = build_demo_readiness_report(project_root=case_root)
  assert len(report.cases) == 3
  assert report.demo_operator_checklist
  assert report.cloud_preparation_checklist
  assert report.no_email_send is True
