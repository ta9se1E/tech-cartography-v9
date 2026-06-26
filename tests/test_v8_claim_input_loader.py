"""Tests for v8 claim input loader (Phase 27E)."""

from __future__ import annotations

from tech_cartography.services.v8_claim_input_loader import (
  CLAIMS_INPUT_COLUMNS,
  load_claim_inputs,
  load_claims_input_csv,
)
from tech_cartography.services.v8_sources_repository import project_root_from_here

CASE_IDS = (
  "case_01_pan_graphitization",
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
)


def test_load_claims_input_csv_all_cases() -> None:
  root = project_root_from_here()
  for case_id in CASE_IDS:
    rows, warnings = load_claims_input_csv(case_id, project_root=root)
    assert len(rows) >= 3
    assert all(r.publication_number for r in rows)
    assert all(r.case_id == case_id for r in rows)
    loaded = [r for r in rows if r.has_loaded_text()]
    if case_id == "case_01_pan_graphitization":
      assert len(loaded) >= 1
      assert all(r.claim_source_type == "manual" for r in loaded)
    else:
      assert not loaded
      for row in rows:
        assert "claim text not loaded" in row.warnings


def test_claims_input_columns_present() -> None:
  root = project_root_from_here()
  rows, _ = load_claims_input_csv("case_01_pan_graphitization", project_root=root)
  assert rows
  sample = rows[0].to_dict()
  for col in CLAIMS_INPUT_COLUMNS:
    assert col in sample


def test_manual_claim_merge() -> None:
  root = project_root_from_here()
  manual = [{
    "publication_number": "US5176959",
    "claim_no": "1",
    "claim_text": "A method comprising carbonizing a PAN precursor fiber at elevated temperature.",
    "patent_title": "manual test",
  }]
  rows, _, _ = load_claim_inputs(
    "case_01_pan_graphitization",
    project_root=root,
    manual_rows=manual,
  )
  manual_row = next(r for r in rows if r.claim_source_type == "manual")
  assert manual_row.has_loaded_text()
