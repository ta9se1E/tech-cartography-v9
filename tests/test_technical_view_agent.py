"""Tests for technical view agent."""

from tech_cartography.agents.technical_view_agent import (
  assess_patent_technical_view,
  build_technical_summary,
  recommend_reader_action,
  run_technical_view_assessment,
)


def _strong_patent_map() -> dict:
  return {
    "publication_number": "US2024000001A1",
    "patent_title": "PAN carbon fiber carbonization",
    "assignee": "Toray",
    "evidence_items": [
      {
        "element_id": "e1",
        "element_type": "material",
        "element_text": "PAN precursor",
        "normalized_terms": ["PAN"],
        "claim_support_status": "supported_by_examples",
        "evidence_relation": "supporting_evidence_candidate",
        "source_quality_level": "high",
        "relevance_score": 0.85,
      },
      {
        "element_id": "e2",
        "element_type": "process",
        "element_text": "carbonization",
        "normalized_terms": ["carbonization"],
        "claim_support_status": "supported_by_examples",
        "evidence_relation": "supporting_evidence_candidate",
        "source_quality_level": "high",
        "relevance_score": 0.8,
      },
      {
        "element_id": "e3",
        "element_type": "property",
        "element_text": "tensile strength",
        "normalized_terms": ["tensile strength"],
        "claim_support_status": "supported_by_measured_properties",
        "evidence_relation": "supporting_evidence_candidate",
        "source_quality_level": "high",
        "relevance_score": 0.82,
      },
    ],
  }


def _weak_patent_map() -> dict:
  return {
    "publication_number": "US2024000002A1",
    "patent_title": "Generic carbon fiber",
    "assignee": "Example Co",
    "evidence_items": [
      {
        "element_id": "e1",
        "element_type": "material",
        "element_text": "carbon fiber",
        "normalized_terms": ["carbon fiber"],
        "claim_support_status": "claim_only",
        "evidence_relation": "no_paper_evidence",
      },
      {
        "element_id": "e2",
        "element_type": "application",
        "element_text": "aerospace composite",
        "normalized_terms": ["aerospace"],
        "claim_support_status": "claim_only",
        "evidence_relation": "weak_match",
        "source_quality_level": "low",
      },
    ],
  }


def test_strong_patent_higher_confidence() -> None:
  assessment = assess_patent_technical_view(_strong_patent_map(), [], [])
  assert assessment["overall_technical_score"] >= 0.45
  assert assessment["overall_technical_confidence"] in {"high", "medium"}


def test_weak_patent_lower_confidence_and_reader_action() -> None:
  gaps = [
    {"publication_number": "US2024000002A1", "element_id": "e1", "gap_type": "no_paper_found"},
    {"publication_number": "US2024000002A1", "element_id": "e2", "gap_type": "weak_only"},
  ]
  assessment = assess_patent_technical_view(_weak_patent_map(), _weak_patent_map()["evidence_items"], gaps)
  assert assessment["overall_technical_score"] < assess_patent_technical_view(_strong_patent_map(), [], [])["overall_technical_score"]
  assert recommend_reader_action(assessment) in {
    "expert_review_required",
    "read_claims_and_examples_first",
    "manual_fulltext_required",
  }


def test_numerical_condition_recommended_check() -> None:
  patent_map = _strong_patent_map()
  patent_map["evidence_items"].append(
    {
      "element_id": "e4",
      "element_type": "numerical_condition",
      "element_text": "850 to 1800 C",
      "normalized_terms": ["850 to 1800 C"],
      "claim_support_status": "claim_only",
      "evidence_relation": "no_paper_evidence",
    },
  )
  assessment = assess_patent_technical_view(patent_map, patent_map["evidence_items"], [])
  checks = " ".join(item.get("recommended_check", "") for item in assessment["assessment_items"])
  assert "example" in checks.lower() or "measurement" in checks.lower() or "numerical" in checks.lower()


def test_summary_avoids_assertive_proof_language() -> None:
  assessment = assess_patent_technical_view(_strong_patent_map(), [], [])
  summary = build_technical_summary(assessment)
  assert "証明" not in summary
  assert "candidate" in summary.lower() or "preliminary" in summary.lower() or "候補" in summary


def test_run_technical_view_assessment() -> None:
  result = run_technical_view_assessment(
    [_strong_patent_map(), _weak_patent_map()],
    _strong_patent_map()["evidence_items"] + _weak_patent_map()["evidence_items"],
    [{"publication_number": "US2024000002A1", "element_id": "e1", "gap_type": "no_paper_found"}],
  )
  assert result["total_patents"] == 2
  assert result["assessment_items"]
