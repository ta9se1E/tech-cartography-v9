"""Quality checks for v8 Evidence Map (Phase 27F)."""

from __future__ import annotations

from tech_cartography.runtime.v8_evidence_map_schema import EVIDENCE_MAP_SAFETY_NOTICES
from tech_cartography.services.v8_evidence_map import build_evidence_map
from tech_cartography.services.v8_sources_repository import project_root_from_here

CASE_IDS = (
  "case_01_pan_graphitization",
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
)


def test_evidence_map_quality_notices() -> None:
  root = project_root_from_here()
  safety = " ".join(EVIDENCE_MAP_SAFETY_NOTICES).lower()
  assert "supporting evidence candidate" in safety
  assert "not proof" in safety or "証明" in safety
  assert "fto" in safety

  for case_id in CASE_IDS:
    emap = build_evidence_map(case_id=case_id, project_root=root)
    assert emap.claim_text_required_count >= 1
    for link in emap.links:
      assert link.no_legal_judgement is True
      assert "evidence_map_not_proof" in link.caution_flags or link.support_type == "claim_text_required"
      assert (
        "supporting_evidence_candidate" in link.caution_flags
        or link.support_type == "claim_text_required"
        or "missing_evidence" in link.caution_flags
      )
      assert "direct" not in link.support_level or "candidate" in link.support_level
