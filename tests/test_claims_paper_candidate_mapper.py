"""Tests for claim × paper candidate mapper (Phase 19)."""

from __future__ import annotations

from tech_cartography.evidence.claims_paper_candidate_mapper import (
  classify_claim_paper_link,
  map_claim_elements_to_paper_candidates,
  render_claim_paper_candidate_map_markdown,
  score_claim_paper_candidate_link,
)


def _element() -> dict:
  return {
    "element_id": "e1",
    "element_type": "material",
    "element_text": "PAN precursor carbon fiber carbonization oxidation",
    "normalized_terms": ["pan", "precursor", "carbonization"],
    "publication_number": "US-12565719-B2",
  }


def _paper() -> dict:
  return {
    "paper_id": "W1",
    "title": "PAN precursor carbonization for high strength carbon fiber",
    "abstract": "oxidation stabilization process manufacturing",
    "publication_number": "US-12565719-B2",
    "query_type": "material_process",
  }


def test_material_process_claim_links_to_paper_title() -> None:
  link = score_claim_paper_candidate_link(_element(), _paper(), has_description=False)
  assert link["link_type"] in {"material_process_background", "weak_background"}
  assert link["confidence"] in {"medium", "low", "weak"}
  assert link["confidence"] != "high"
  assert float(link["link_score"]) > 0


def test_unrelated_or_weak_for_irrelevant_paper() -> None:
  unrelated = {
    "paper_id": "W9",
    "title": "Quantum computing error correction",
    "abstract": "qubit decoherence",
  }
  link = score_claim_paper_candidate_link(_element(), unrelated, has_description=False)
  assert classify_claim_paper_link(link) in {"unrelated", "weak_background"}
  links = map_claim_elements_to_paper_candidates([_element()], [unrelated], has_description=False)
  assert len(links) == 0 or all(row["link_type"] != "material_process_background" for row in links)


def test_no_high_confidence_without_description() -> None:
  link = score_claim_paper_candidate_link(_element(), _paper(), has_description=False)
  assert link["confidence"] != "high"


def test_caveat_when_no_description() -> None:
  link = score_claim_paper_candidate_link(_element(), _paper(), has_description=False)
  assert "caveat_japanese" in link
  assert "supporting" in link["caveat_japanese"].lower() or "明細書" in link["caveat_japanese"]
  md = render_claim_paper_candidate_map_markdown(
    map_claim_elements_to_paper_candidates([_element()], [_paper()], has_description=False),
  )
  assert "$" not in md
  assert "supporting" in md.lower() or "Candidate" in md


def test_likely_off_topic_not_linked() -> None:
  off_topic = {
    "paper_id": "W-off",
    "title": "Quantum computing error correction",
    "abstract": "qubit decoherence",
    "relevance_bucket": "likely_off_topic",
    "relevance_score": 0.0,
  }
  links = map_claim_elements_to_paper_candidates([_element()], [off_topic], has_description=False)
  assert links == []


def test_relevance_bucket_in_link() -> None:
  paper = _paper()
  paper["relevance_bucket"] = "strong_material_process_background"
  paper["relevance_score"] = 0.6
  link = score_claim_paper_candidate_link(_element(), paper, has_description=False)
  assert link.get("relevance_bucket") == "strong_material_process_background"


def test_broad_composite_background_becomes_weak_link() -> None:
  broad = {
    "paper_id": "W-broad",
    "title": "Natural Fiber Reinforced Composites review",
    "abstract": "hemp fiber general composite",
    "relevance_bucket": "broad_composite_background",
    "relevance_score": 0.2,
  }
  link = score_claim_paper_candidate_link(_element(), broad, has_description=False)
  assert link["link_type"] == "weak_background"
