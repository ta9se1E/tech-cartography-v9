"""Tests for v8 Evidence Map service (Phase 27F)."""

from __future__ import annotations

from tech_cartography.services.v8_claim_map import build_claim_record
from tech_cartography.services.v8_claim_input_loader import V8ClaimInputRow
from tech_cartography.services.v8_evidence_map import build_evidence_map
from tech_cartography.services.v8_sources_repository import project_root_from_here

CASE_IDS = (
  "case_01_pan_graphitization",
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
)

MANUAL_CLAIM = (
  "A method comprising stabilizing a PAN precursor fiber and carbonizing "
  "to obtain tensile strength and modulus."
)


def test_build_evidence_map_all_cases() -> None:
  root = project_root_from_here()
  for case_id in CASE_IDS:
    emap = build_evidence_map(case_id=case_id, project_root=root)
    assert emap.link_count >= 1
    assert emap.claim_count >= 1
    assert emap.count_by_support_type
    assert emap.count_by_support_level
    for link in emap.links:
      assert link.next_verification_action.strip()


def test_claim_text_required_links() -> None:
  root = project_root_from_here()
  emap = build_evidence_map(case_id="case_02_sizing_interface", project_root=root)
  required = [l for l in emap.links if l.support_type == "claim_text_required"]
  assert required
  assert required[0].support_level in {"missing", "needs_human_review"}
  assert "claim text" in required[0].evidence_gap.lower()


def test_loaded_claim_paper_candidate() -> None:
  root = project_root_from_here()
  from tech_cartography.runtime.v8_claim_map_schema import V8ClaimMap
  from tech_cartography.services.v8_claim_map import build_claim_map

  claim_map = build_claim_map(case_id="case_01_pan_graphitization", project_root=root)
  manual_row = V8ClaimInputRow(
    case_id="case_01_pan_graphitization",
    publication_number="US5176959",
    claim_no="1",
    claim_text=MANUAL_CLAIM,
    claim_source_type="manual",
  )
  claim_map.records = [build_claim_record(manual_row, case_id="case_01_pan_graphitization")]
  claim_map.claim_count = 1
  claim_map.loaded_claim_count = 1
  claim_map.not_loaded_claim_count = 0

  emap = build_evidence_map(
    case_id="case_01_pan_graphitization",
    project_root=root,
    claim_map=claim_map,
  )
  paper_links = [l for l in emap.links if l.support_type == "paper_support_candidate"]
  assert paper_links
  assert paper_links[0].support_level == "medium_candidate"
  assert "candidate" in paper_links[0].match_reason.lower()


def test_web_company_weak_candidate() -> None:
  root = project_root_from_here()
  from tech_cartography.services.v8_claim_map import build_claim_record

  manual_row = V8ClaimInputRow(
    case_id="case_02_sizing_interface",
    publication_number="US5916936",
    claim_no="1",
    claim_text="A sizing composition for carbon fibers improving interfacial adhesion with epoxy matrix composite.",
    claim_source_type="manual",
  )
  from tech_cartography.services.v8_claim_map import build_claim_map

  claim_map = build_claim_map(case_id="case_02_sizing_interface", project_root=root)
  claim_map.records = [build_claim_record(manual_row, case_id="case_02_sizing_interface")]

  emap = build_evidence_map(
    case_id="case_02_sizing_interface",
    project_root=root,
    claim_map=claim_map,
  )
  web_links = [l for l in emap.links if l.source_type in {"web", "company"}]
  assert web_links
  for link in web_links:
    assert link.support_level in {"weak_candidate", "needs_human_review"}
