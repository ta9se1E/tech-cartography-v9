"""Tests for v8 patent shortlist service (Phase 27D)."""

from __future__ import annotations

from tech_cartography.services.v8_patent_shortlist import build_patent_shortlist
from tech_cartography.services.v8_sources_repository import project_root_from_here

CASE_IDS = (
  "case_01_pan_graphitization",
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
)


def test_build_patent_shortlist_all_cases_top3() -> None:
  root = project_root_from_here()
  for case_id in CASE_IDS:
    shortlist = build_patent_shortlist(case_id=case_id, top_n=3, project_root=root)
    assert shortlist.case_id == case_id
    assert len(shortlist.patent_candidates) >= 3
    for candidate in shortlist.patent_candidates:
      assert isinstance(candidate.total_score, float)
      assert candidate.score_breakdown
      assert candidate.why_read.strip()
      assert candidate.next_verification_action.strip()
      assert "claim text not loaded" in candidate.why_read.lower() or "claim text not loaded" in " ".join(
        candidate.caution_flags,
      ).lower()


def test_shortlist_top5_per_case() -> None:
  root = project_root_from_here()
  for case_id in CASE_IDS:
    shortlist = build_patent_shortlist(case_id=case_id, top_n=5, project_root=root)
    assert shortlist.top_n == 5
    assert shortlist.count <= 5
    ranks = [c.rank for c in shortlist.patent_candidates]
    assert ranks == list(range(1, len(ranks) + 1))
