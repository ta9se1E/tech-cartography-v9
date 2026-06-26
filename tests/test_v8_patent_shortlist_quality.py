"""Quality checks for v8 patent shortlist (Phase 27D)."""

from __future__ import annotations

from tech_cartography.runtime.v8_patent_shortlist_schema import SHORTLIST_SAFETY_NOTICES
from tech_cartography.services.v8_patent_shortlist import build_patent_shortlist
from tech_cartography.services.v8_sources_repository import project_root_from_here

CASE_IDS = (
  "case_01_pan_graphitization",
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
)


def test_shortlist_quality_scores_and_notices() -> None:
  root = project_root_from_here()
  safety_blob = " ".join(SHORTLIST_SAFETY_NOTICES).lower()
  assert "特許価値" in safety_blob or "権利価値" in safety_blob
  assert "fto" in safety_blob

  for case_id in CASE_IDS:
    shortlist = build_patent_shortlist(case_id=case_id, top_n=5, project_root=root)
    assert len(shortlist.patent_candidates) >= 3
    for candidate in shortlist.patent_candidates:
      assert candidate.no_legal_judgement is True
      assert "heuristic" in candidate.why_read.lower() or "draft" in candidate.why_read.lower()
      assert "reading_priority_not_patent_value" in candidate.caution_flags
      assert "claim_text_not_loaded" in candidate.caution_flags
      assert "no_legal_judgement" in candidate.caution_flags
      assert candidate.key_claim_focus.startswith("claim text not loaded")
