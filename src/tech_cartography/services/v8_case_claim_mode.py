"""Case claim input mode helpers (Phase 27Q.2)."""

from __future__ import annotations

CASE_01_ID = "case_01_pan_graphitization"

CASE_01_FULL_MANUAL_CLAIM_COUNT = 35

CASE_01_PUB_CLAIM_COUNTS: dict[str, int] = {
  "CN105401262A": 3,
  "CN105506785B": 7,
  "CN108286090A": 8,
  "CN109402791B": 6,
  "CN117987966A": 11,
}

INCOMPLETE_CLAIM_CASE_IDS: frozenset[str] = frozenset({
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
})


def is_full_manual_claims_mode(case_id: str) -> bool:
  """Case 1 Top5 — all claims loaded via manual_input."""
  return case_id == CASE_01_ID


def expects_claim_text_required_links(case_id: str) -> bool:
  return case_id in INCOMPLETE_CLAIM_CASE_IDS
