"""Tests for evidence gap analyzer."""

from tech_cartography.evidence.evidence_gap_analyzer import (
  analyze_evidence_gaps,
  classify_gap_type,
)


def _element(**overrides) -> dict:
  base = {
    "publication_number": "US1",
    "element_id": "e1",
    "element_type": "process",
    "element_text": "surface treatment",
    "normalized_terms": ["surface treatment"],
    "support_status": "claim_only",
  }
  base.update(overrides)
  return base


def test_no_paper_found_gap() -> None:
  gap_type = classify_gap_type(_element(), [])
  assert gap_type == "no_paper_found"
  gaps = analyze_evidence_gaps(
    [
      {
        "element_id": "e1",
        "publication_number": "US1",
        "evidence_relation": "no_paper_evidence",
      },
    ],
    [_element()],
  )
  assert any(gap["gap_type"] == "no_paper_found" for gap in gaps)


def test_background_only_gap() -> None:
  items = [
    {
      "element_id": "e1",
      "publication_number": "US1",
      "evidence_relation": "background_evidence",
      "source_quality_level": "medium",
    },
  ]
  gap_type = classify_gap_type(_element(support_status="supported_by_description"), items)
  assert gap_type == "background_only"


def test_claim_only_no_description_support_gap() -> None:
  element = _element(support_status="claim_only")
  items = [
    {
      "element_id": "e1",
      "publication_number": "US1",
      "evidence_relation": "background_evidence",
      "source_quality_level": "medium",
    },
  ]
  gap_type = classify_gap_type(element, items)
  assert gap_type == "claim_only_no_description_support"
