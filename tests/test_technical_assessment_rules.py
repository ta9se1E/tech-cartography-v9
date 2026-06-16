"""Tests for technical assessment rules."""

from tech_cartography.agents.technical_assessment_rules import (
  score_claim_only_risk,
  score_description_support,
  score_evidence_strength,
  score_material_process_property_linkage,
  score_measurement_support,
  score_overall_technical_confidence,
  score_paper_support,
)


def _patent_map(items: list[dict]) -> dict:
  return {
    "publication_number": "US1",
    "patent_title": "Carbon fiber process",
    "evidence_items": items,
  }


def test_supporting_evidence_increases_score() -> None:
  strong = _patent_map(
    [
      {
        "evidence_relation": "supporting_evidence_candidate",
        "source_quality_level": "high",
        "claim_support_status": "supported_by_examples",
      },
      {
        "evidence_relation": "supporting_evidence_candidate",
        "source_quality_level": "high",
        "claim_support_status": "supported_by_measured_properties",
      },
    ],
  )
  weak = _patent_map(
    [
      {"evidence_relation": "no_paper_evidence", "claim_support_status": "claim_only"},
      {"evidence_relation": "weak_match", "claim_support_status": "claim_only"},
    ],
  )
  assert score_evidence_strength(strong)["score"] > score_evidence_strength(weak)["score"]


def test_examples_increase_description_support() -> None:
  with_examples = _patent_map(
    [{"claim_support_status": "supported_by_examples"}],
  )
  claim_only = _patent_map(
    [{"claim_support_status": "claim_only"}],
  )
  assert score_description_support(with_examples)["score"] > score_description_support(claim_only)["score"]


def test_claim_only_risk() -> None:
  result = score_claim_only_risk(
    _patent_map(
      [
        {"claim_support_status": "claim_only"},
        {"claim_support_status": "claim_only"},
      ],
    ),
    [{"gap_type": "claim_only_no_description_support"}],
  )
  assert result["score"] >= 0.4
  assert result["human_review_required"]


def test_material_process_property_linkage() -> None:
  linked = _patent_map(
    [
      {"element_type": "material", "normalized_terms": ["PAN"]},
      {"element_type": "process", "normalized_terms": ["carbonization"]},
      {"element_type": "property", "normalized_terms": ["tensile strength"]},
    ],
  )
  single = _patent_map(
    [{"element_type": "material", "normalized_terms": ["carbon fiber"]}],
  )
  assert score_material_process_property_linkage(linked)["score"] > score_material_process_property_linkage(single)["score"]


def test_low_quality_paper_support_caps_confidence() -> None:
  scores = {
    "evidence_strength": score_evidence_strength(
      _patent_map(
        [{"evidence_relation": "supporting_evidence_candidate", "source_quality_level": "low"}],
      ),
    ),
    "description_support": score_description_support(_patent_map([])),
    "paper_support": score_paper_support(
      _patent_map(
        [{"evidence_relation": "supporting_evidence_candidate", "source_quality_level": "low"}],
      ),
    ),
    "measurement_support": score_measurement_support(_patent_map([])),
    "implementation_risk": {"score": 0.2},
    "claim_only_risk": {"score": 0.2, "human_review_required": False},
    "material_process_property": score_material_process_property_linkage(_patent_map([])),
  }
  overall = score_overall_technical_confidence(scores)
  assert overall["overall_score"] <= 0.65


def test_numerical_condition_measurement_risk() -> None:
  result = score_measurement_support(
    _patent_map(
      [
        {"element_type": "numerical_condition", "element_text": "850 to 1800 C", "claim_support_status": "claim_only"},
        {"element_type": "property", "element_text": "tensile strength", "claim_support_status": "claim_only"},
      ],
    ),
  )
  assert result["numerical_count"] >= 1
  assert result["property_without_measurement"]
