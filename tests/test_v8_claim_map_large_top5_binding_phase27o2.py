"""Phase27O.2 — Large Candidate Top5 vs legacy shortlist binding."""

from __future__ import annotations

from tech_cartography.services.v8_claim_map import build_claim_map
from tech_cartography.services.v8_deep_dive_shortlist import list_deep_dive_publications, resolve_deep_dive_shortlist
from tech_cartography.services.v8_large_candidate_shortlist import load_top5_publications
from tech_cartography.services.v8_manual_claim_injection import list_claims_needing_text
from tech_cartography.services.v8_sources_table import project_root_from_here

CASE_ID = "case_01_pan_graphitization"
CN_TOP5 = (
  "CN108286090A",
  "CN117987966A",
  "CN105401262A",
  "CN105506785B",
  "CN109402791B",
)


def test_large_candidate_top5_preferred_over_legacy_us() -> None:
  root = project_root_from_here()
  top5 = load_top5_publications(CASE_ID, root)
  if not top5:
    return
  assert top5[0].startswith("CN")
  assert "US5176959" not in top5


def test_deep_dive_shortlist_uses_cn_top5_when_pack_exists() -> None:
  root = project_root_from_here()
  top5 = load_top5_publications(CASE_ID, root)
  if not top5:
    return
  shortlist = resolve_deep_dive_shortlist(CASE_ID, root)
  pubs = [p.publication_number for p in shortlist.patent_candidates]
  assert pubs == top5[:5]
  assert "legacy_patent_shortlist_fallback" not in " ".join(shortlist.warnings)


def test_claims_needing_text_excludes_legacy_us_when_top5_exists() -> None:
  root = project_root_from_here()
  if not load_top5_publications(CASE_ID, root):
    return
  needing = list_claims_needing_text(CASE_ID, project_root=root)
  pubs = [n["publication_number"] for n in needing]
  assert "US5176959" not in pubs
  assert "US4370169" not in pubs
  assert "CN108286090A" not in pubs


def test_claims_needing_text_cn_top5_only() -> None:
  root = project_root_from_here()
  pubs, source = list_deep_dive_publications(CASE_ID, root)
  if source != "large_candidate_top5":
    return
  needing = list_claims_needing_text(CASE_ID, project_root=root)
  needing_pubs = {n["publication_number"] for n in needing}
  assert needing_pubs.issubset(set(CN_TOP5))
  assert "CN108286090A" not in needing_pubs


def test_full_top5_claim_map_includes_manual_input_cn() -> None:
  root = project_root_from_here()
  if not load_top5_publications(CASE_ID, root):
    return
  claim_map = build_claim_map(case_id=CASE_ID, publication_number=None, project_root=root)
  assert claim_map.claim_count == 5
  loaded_pubs = {r.publication_number for r in claim_map.records if r.claim_text_status != "not_loaded"}
  assert "CN108286090A" in loaded_pubs
