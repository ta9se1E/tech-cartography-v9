"""Tests for v8 Gap / Next Actions service (Phase 27G)."""

from __future__ import annotations

from tech_cartography.services.v8_gap_next_actions import build_gap_next_actions_report
from tech_cartography.services.v8_sources_repository import project_root_from_here

CASE_IDS = (
  "case_01_pan_graphitization",
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
)


def test_build_gap_report_all_cases() -> None:
  root = project_root_from_here()
  for case_id in CASE_IDS:
    report = build_gap_next_actions_report(case_id=case_id, project_root=root)
    assert report.gap_count >= 1
    assert report.action_count >= 1
    assert len(report.top_3_actions) >= 1
    assert report.watch_profile_update_proposal.strip()
    assert report.digest_summary.strip()
    assert report.no_legal_judgement is True


def test_claim_text_required_maps_to_load_claim_text() -> None:
  root = project_root_from_here()
  report = build_gap_next_actions_report(case_id="case_01_pan_graphitization", project_root=root)
  claim_gaps = [g for g in report.gaps if g.gap_type == "claim_text_required"]
  assert claim_gaps
  top = report.top_3_actions[0]
  assert top.action_type == "load_claim_text"
  assert "claim" in top.action_title.lower()


def test_missing_evidence_action_types() -> None:
  root = project_root_from_here()
  report = build_gap_next_actions_report(case_id="case_01_pan_graphitization", project_root=root)
  gap_types = {g.gap_type for g in report.gaps}
  action_types = {a.action_type for a in report.next_actions}
  if "example_support_missing" in gap_types:
    assert "check_patent_examples" in action_types
  if "paper_support_missing" in gap_types:
    assert "check_paper_source" in action_types or "expand_paper_search" in action_types


def test_artifact_paths_in_report() -> None:
  root = project_root_from_here()
  report = build_gap_next_actions_report(case_id="case_01_pan_graphitization", project_root=root)
  assert isinstance(report.source_artifact_paths, list)
  assert isinstance(report.evidence_map_artifact_paths, list)
