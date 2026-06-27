"""Phase27O.2 — manual claim to Claim Map binding."""

from __future__ import annotations

from tech_cartography.services.v8_claim_input_loader import load_claims_input_csv
from tech_cartography.services.v8_claim_map import build_claim_map, build_claim_record
from tech_cartography.services.v8_sources_table import project_root_from_here

CASE_ID = "case_01_pan_graphitization"
PUB = "CN108286090A"


def test_manual_input_row_loaded_from_claims_input_csv() -> None:
  root = project_root_from_here()
  rows, _ = load_claims_input_csv(CASE_ID, project_root=root)
  row = next((r for r in rows if r.publication_number == PUB), None)
  assert row is not None
  assert row.claim_source_type == "manual"
  assert row.has_loaded_text()
  assert row.claim_no == "1"


def test_manual_source_type_maps_to_manual_input_status() -> None:
  root = project_root_from_here()
  rows, _ = load_claims_input_csv(CASE_ID, project_root=root)
  row = next(r for r in rows if r.publication_number == PUB)
  record = build_claim_record(row, case_id=CASE_ID)
  assert record.claim_text_status == "manual_input"
  assert record.claim_text != "claim text not loaded"
  assert "claim_text_loading_required" not in record.evidence_needed


def test_selected_cn108286090a_produces_all_loaded_claims() -> None:
  root = project_root_from_here()
  claim_map = build_claim_map(
    case_id=CASE_ID,
    publication_number=PUB,
    project_root=root,
  )
  assert claim_map.claim_count == 8
  assert claim_map.loaded_claim_count == 8
  assert claim_map.not_loaded_claim_count == 0
  assert all(r.publication_number == PUB for r in claim_map.records)
  assert all(r.claim_text_status == "manual_input" for r in claim_map.records)


def test_claim_map_not_zero_when_manual_input_exists() -> None:
  root = project_root_from_here()
  claim_map = build_claim_map(case_id=CASE_ID, publication_number=PUB, project_root=root)
  assert claim_map.claim_count >= 1
  assert claim_map.loaded_claim_count >= 1
