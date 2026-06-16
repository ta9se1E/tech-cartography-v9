"""Tests for claim-paper evidence map builder."""

from tech_cartography.evidence.claim_paper_evidence_map import build_claim_paper_evidence_map


def _element(**overrides) -> dict:
  base = {
    "publication_number": "US2024000001A1",
    "title": "PAN carbon fiber process",
    "assignee": "Toray",
    "element_id": "e1",
    "element_type": "process",
    "element_text": "surface treatment and interface adhesion",
    "normalized_terms": ["surface treatment", "interface adhesion"],
    "support_status": "supported_by_examples",
  }
  base.update(overrides)
  return base


def _link(**overrides) -> dict:
  base = {
    "publication_number": "US2024000001A1",
    "element_id": "e1",
    "element_type": "process",
    "element_text": "surface treatment and interface adhesion",
    "paper_id": "W1",
    "paper_title": "Carbon fiber surface treatment for interface adhesion",
    "paper_year": 2020,
    "source_name": "Carbon Journal",
    "doi": "10.1000/test",
    "display_url": "https://example.org/paper",
    "source_quality_level": "high",
    "source_quality_score": 0.9,
    "evidence_relation": "supporting_evidence_candidate",
    "relevance_score": 0.85,
    "matched_terms": ["surface treatment", "interface adhesion"],
    "relation_reason": "matched_terms=surface treatment, interface adhesion",
    "recommended_use": "cite_as_evidence_candidate",
  }
  base.update(overrides)
  return base


def test_build_map_with_supporting_link() -> None:
  result = build_claim_paper_evidence_map(
    [_element()],
    [_link()],
    paper_records=[{"paper_id": "W1", "title": "Carbon fiber surface treatment for interface adhesion"}],
    source_quality_results=[{"source_id": "W1", "quality_level": "high", "quality_score": 0.9}],
  )
  assert result["total_evidence_items"] >= 1
  assert result["supporting_evidence_candidates"] + result["strong_evidence_candidates"] >= 1
  assert len(result["patent_evidence_maps"]) == 1


def test_no_link_creates_no_paper_evidence_item() -> None:
  result = build_claim_paper_evidence_map([_element(element_id="e2")], [])
  assert result["no_paper_evidence_items"] >= 1
  item = next(item for item in result["evidence_items"] if item["element_id"] == "e2")
  assert item["evidence_relation"] == "no_paper_evidence"


def test_element_type_summary() -> None:
  result = build_claim_paper_evidence_map(
    [_element(), _element(element_id="e2", element_type="material", normalized_terms=["PAN"])],
    [_link()],
  )
  types = {row["element_type"] for row in result["evidence_by_element_type"]}
  assert "process" in types
  assert "material" in types


def test_material_process_property_score_boost() -> None:
  result = build_claim_paper_evidence_map(
    [
      _element(
        element_type="property",
        normalized_terms=["PAN", "carbonization", "tensile strength"],
      ),
    ],
    [
      _link(
        element_id="e1",
        matched_terms=["PAN", "carbonization", "tensile strength"],
        evidence_relation="supporting_evidence_candidate",
        relevance_score=0.9,
      ),
    ],
  )
  item = result["evidence_items"][0]
  assert float(item["evidence_score"]) >= 0.5
