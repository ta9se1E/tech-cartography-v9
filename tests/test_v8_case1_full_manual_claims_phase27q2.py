"""Phase27Q.2 — Case 1 full Top5 manual claims mode."""

from __future__ import annotations

from tech_cartography.services.v8_case_claim_mode import (
  CASE_01_FULL_MANUAL_CLAIM_COUNT,
  CASE_01_ID,
  CASE_01_PUB_CLAIM_COUNTS,
)
from tech_cartography.services.v8_claim_map import build_claim_map
from tech_cartography.services.v8_evidence_map import build_evidence_map
from tech_cartography.services.v8_gap_next_actions import build_gap_next_actions_report
from tech_cartography.services.v8_sources_table import project_root_from_here


def test_case1_full_manual_claim_map() -> None:
  root = project_root_from_here()
  claim_map = build_claim_map(case_id=CASE_01_ID, project_root=root)
  assert claim_map.claim_count == CASE_01_FULL_MANUAL_CLAIM_COUNT
  assert claim_map.not_loaded_claim_count == 0
  assert claim_map.loaded_claim_count == CASE_01_FULL_MANUAL_CLAIM_COUNT


def test_case1_per_patent_claim_counts() -> None:
  root = project_root_from_here()
  for pub, expected in CASE_01_PUB_CLAIM_COUNTS.items():
    claim_map = build_claim_map(case_id=CASE_01_ID, publication_number=pub, project_root=root)
    assert claim_map.claim_count == expected
    assert claim_map.not_loaded_claim_count == 0


def test_case1_no_claim_text_required_in_evidence_map() -> None:
  root = project_root_from_here()
  evidence = build_evidence_map(case_id=CASE_01_ID, project_root=root)
  assert evidence.claim_text_required_count == 0
  assert evidence.link_count >= CASE_01_FULL_MANUAL_CLAIM_COUNT
  assert not any(l.support_type == "claim_text_required" for l in evidence.links)


def test_case1_gap_report_after_full_manual_claims() -> None:
  root = project_root_from_here()
  gap = build_gap_next_actions_report(case_id=CASE_01_ID, project_root=root)
  assert gap.gap_count >= 1
  assert gap.count_by_gap_type.get("claim_text_required", 0) == 0
  assert len(gap.top_3_actions) >= 1
  assert gap.top_3_actions[0].action_type != "load_claim_text"


def test_case2_case3_incomplete_mode_still_has_claim_text_required() -> None:
  root = project_root_from_here()
  for case_id in ("case_02_sizing_interface", "case_03_pressure_vessel_filament_winding"):
    evidence = build_evidence_map(case_id=case_id, project_root=root)
    assert evidence.claim_text_required_count >= 1
    assert any(l.support_type == "claim_text_required" for l in evidence.links)
