"""Tests for v8 Claim Map service (Phase 27E)."""

from __future__ import annotations

from tech_cartography.services.v8_claim_map import build_claim_map, build_claim_record
from tech_cartography.services.v8_claim_input_loader import V8ClaimInputRow
from tech_cartography.services.v8_sources_repository import project_root_from_here

CASE_IDS = (
  "case_01_pan_graphitization",
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
)

MANUAL_CLAIM = (
  "1. A method for producing carbon fibers comprising stabilizing a PAN precursor fiber "
  "and carbonizing the stabilized fiber to obtain tensile strength and modulus."
)


def test_build_claim_map_not_loaded_all_cases() -> None:
  root = project_root_from_here()
  for case_id in CASE_IDS:
    claim_map = build_claim_map(case_id=case_id, project_root=root)
    assert claim_map.claim_count >= 3
    for rec in claim_map.records:
      assert rec.claim_text_status == "not_loaded"
      assert rec.next_evidence_check.strip()
      assert "claim_text_loading_required" in rec.evidence_needed


def test_manual_claim_classification() -> None:
  row = V8ClaimInputRow(
    case_id="case_01_pan_graphitization",
    publication_number="US5176959",
    patent_title="PAN carbon fiber",
    claim_no="1",
    claim_text=MANUAL_CLAIM,
    claim_source_type="manual",
  )
  record = build_claim_record(row, case_id="case_01_pan_graphitization")
  assert record.claim_text_status == "manual_input"
  assert record.primary_axis != "unknown"
  assert record.technical_axis_labels
  assert record.process_terms
  assert record.property_terms
  assert record.evidence_needed
  assert "example_support" in record.evidence_needed


def test_not_loaded_does_not_infer_axes() -> None:
  row = V8ClaimInputRow(
    case_id="case_01_pan_graphitization",
    publication_number="US5176959",
    claim_no="1",
    claim_text="",
    claim_source_type="unavailable",
  )
  record = build_claim_record(row, case_id="case_01_pan_graphitization")
  assert record.primary_axis == "unknown"
  assert record.material_terms == []
