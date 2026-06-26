"""Tests for v8 case validation pack service (Phase 27I)."""

from __future__ import annotations

from tech_cartography.runtime.v8_case_validation_schema import VALIDATION_STEP_IDS
from tech_cartography.services.v8_case_validation_pack import (
  build_case_validation_report,
  build_three_case_validation_pack,
)
from tech_cartography.services.v8_sources_table import project_root_from_here

CASE_IDS = (
  "case_01_pan_graphitization",
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
)


def test_build_three_case_validation_pack() -> None:
  root = project_root_from_here()
  pack = build_three_case_validation_pack(project_root=root, ensure_artifacts=False)
  assert len(pack.cases) == 3
  assert pack.total_cases == 3
  assert pack.common_blocking_issues
  assert pack.common_next_actions
  assert pack.demo_readiness_summary.strip()
  assert pack.cloud_readiness_summary.strip()
  assert pack.no_email_send is True
  assert pack.no_scheduler_start is True


def test_each_case_has_all_validation_steps() -> None:
  root = project_root_from_here()
  for case_id in CASE_IDS:
    report = build_case_validation_report(case_id, project_root=root, ensure_artifacts=False)
    step_ids = {s.step_id for s in report.step_results}
    assert step_ids == set(VALIDATION_STEP_IDS)
    assert report.no_legal_judgement is True


def test_claim_text_not_loaded_readiness() -> None:
  root = project_root_from_here()
  report = build_case_validation_report(
    "case_01_pan_graphitization",
    project_root=root,
    ensure_artifacts=False,
  )
  claim_step = next(s for s in report.step_results if s.step_id == "claim_map")
  if claim_step.key_counts.get("not_loaded_count", 0) > 0:
    assert report.readiness_for_demo == "needs_claim_text"
    assert report.overall_status in {"warning", "fail"}


def test_no_fabricated_claim_text_in_claim_map_step() -> None:
  root = project_root_from_here()
  report = build_case_validation_report(
    "case_01_pan_graphitization",
    project_root=root,
    ensure_artifacts=False,
  )
  claim_step = next(s for s in report.step_results if s.step_id == "claim_map")
  loaded = claim_step.key_counts.get("claim_text_loaded", 0)
  not_loaded = claim_step.key_counts.get("not_loaded_count", 0)
  if loaded == 0 and not_loaded > 0:
    assert any("not_loaded" in w or "空欄" in w for w in claim_step.warnings)
