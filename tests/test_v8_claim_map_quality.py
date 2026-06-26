"""Quality checks for v8 Claim Map (Phase 27E)."""

from __future__ import annotations

from tech_cartography.runtime.v8_claim_map_schema import CLAIM_MAP_SAFETY_NOTICES
from tech_cartography.services.v8_claim_map import build_claim_map, build_claim_record
from tech_cartography.services.v8_claim_input_loader import V8ClaimInputRow
from tech_cartography.services.v8_sources_repository import project_root_from_here

CASE_IDS = (
  "case_01_pan_graphitization",
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
)


def test_claim_map_quality_notices_and_labels() -> None:
  root = project_root_from_here()
  safety = " ".join(CLAIM_MAP_SAFETY_NOTICES).lower()
  assert "fto" in safety
  assert "claim text not loaded" in safety

  for case_id in CASE_IDS:
    claim_map = build_claim_map(case_id=case_id, project_root=root)
    assert claim_map.not_loaded_claim_count >= 1
    for rec in claim_map.records:
      assert rec.no_legal_judgement is True
      assert "no_legal_judgement" in rec.caution_flags
      if rec.claim_text_status == "not_loaded":
        assert "claim_text_not_loaded" in rec.caution_flags


def test_case2_sizing_axis_on_manual_claim() -> None:
  row = V8ClaimInputRow(
    case_id="case_02_sizing_interface",
    publication_number="US5916936",
    claim_no="1",
    claim_text="A sizing composition for carbon fibers improving interfacial adhesion with epoxy matrix composite.",
    claim_source_type="manual",
  )
  record = build_claim_record(row, case_id="case_02_sizing_interface")
  axes = " ".join(record.technical_axis_labels).lower()
  assert "sizing" in axes or "matrix" in axes
