"""Phase27O.2 — Evidence Map / Gap binding for manual_input claims."""

from __future__ import annotations

from tech_cartography.services.v8_claim_map import build_claim_map
from tech_cartography.services.v8_evidence_map import build_evidence_map
from tech_cartography.services.v8_gap_next_actions import build_gap_next_actions_report
from tech_cartography.services.v8_large_candidate_shortlist import load_top5_publications
from tech_cartography.services.v8_sources_table import project_root_from_here

CASE_ID = "case_01_pan_graphitization"
PUB = "CN108286090A"


def test_evidence_map_manual_claim_count_for_cn108286090a() -> None:
  root = project_root_from_here()
  claim_map = build_claim_map(case_id=CASE_ID, publication_number=PUB, project_root=root)
  evidence = build_evidence_map(
    case_id=CASE_ID,
    publication_number=PUB,
    project_root=root,
    claim_map=claim_map,
  )
  assert evidence.claim_text_required_count == 0
  assert evidence.claim_count == 1
  assert any(l.publication_number == PUB for l in evidence.links)
  assert not any(l.publication_number == "US5176959" for l in evidence.links)


def test_gap_does_not_ask_claim_load_for_cn108286090a() -> None:
  root = project_root_from_here()
  if not load_top5_publications(CASE_ID, root):
    return
  gap = build_gap_next_actions_report(case_id=CASE_ID, publication_number=PUB, project_root=root)
  claim_gaps = [g for g in gap.gaps if g.gap_type == "claim_text_required" and g.publication_number == PUB]
  assert not claim_gaps
  load_actions = [
    a for a in gap.next_actions
    if a.action_type == "load_claim_text" and a.target_publication_number == PUB
  ]
  assert not load_actions


def test_gap_top_actions_not_us5176959_claim_fetch() -> None:
  root = project_root_from_here()
  gap = build_gap_next_actions_report(case_id=CASE_ID, publication_number=PUB, project_root=root)
  titles = [a.action_title for a in gap.top_3_actions]
  assert not any("US5176959" in t for t in titles)
  assert not any(a.action_type == "load_claim_text" for a in gap.top_3_actions)


def test_safety_notices_preserved_in_gap_report() -> None:
  root = project_root_from_here()
  gap = build_gap_next_actions_report(case_id=CASE_ID, publication_number=PUB, project_root=root)
  text = " ".join(gap.warnings)
  assert "invalidity" in text.lower() or "弱点" in text or "FTO" in text
