"""Tests for business view agent."""

from tech_cartography.agents.business_view_agent import (
  assess_patent_business_view,
  build_business_summary,
  run_business_view_assessment,
)


def _technical_summary(**overrides) -> dict:
  base = {
    "publication_number": "US2024000001A1",
    "patent_title": "Carbon fiber prepreg aerospace",
    "assignee": "TORAY",
    "overall_technical_confidence": "high",
    "overall_technical_score": 0.75,
    "weak_or_uncertain_points": [],
    "key_evidence_gaps": [],
  }
  base.update(overrides)
  return base


def _web_links(**overrides) -> list[dict]:
  link = {
    "publication_number": "US2024000001A1",
    "relation": "business_signal_candidate",
    "signal_type": "production_expansion",
    "source_quality_level": "high",
    "source_title": "Prepreg capacity expansion",
    "relation_reason": "company_match=exact; matched_terms=prepreg",
    "caveat": "Web signal candidate only.",
  }
  link.update(overrides)
  return [link]


def test_business_score_with_signals() -> None:
  assessment = assess_patent_business_view(
    {"publication_number": "US2024000001A1", "assignee": "TORAY", "primary_cluster_id": "bundle_prepreg"},
    _technical_summary(),
    _technical_summary(),
    _web_links(),
  )
  assert assessment["overall_business_score"] >= 0.45
  assert assessment["recommended_reader_action"]


def test_human_review_when_technical_low_business_high() -> None:
  assessment = assess_patent_business_view(
    {"publication_number": "US2024000001A1", "assignee": "TORAY"},
    _technical_summary(overall_technical_confidence="low", overall_technical_score=0.2),
    _technical_summary(overall_technical_confidence="low", overall_technical_score=0.2),
    _web_links(),
  )
  assert assessment["recommended_reader_action"] == "expert_ip_review_required"


def test_summary_no_proof_language() -> None:
  assessment = assess_patent_business_view(
    {"publication_number": "US1", "primary_cluster_name": "bundle_prepreg"},
    _technical_summary(publication_number="US1"),
    _technical_summary(publication_number="US1"),
    _web_links(publication_number="US1"),
  )
  summary = build_business_summary(assessment)
  assert "事業化を証明" not in summary
  assert "参入できる" not in summary
  assert "candidate" in summary.lower() or "候補" in summary or "screening" in summary.lower()


def test_run_business_view_assessment() -> None:
  result = run_business_view_assessment(
    [_technical_summary()],
    [_technical_summary()],
    _web_links(),
    ranked_patents=[
      {
        "publication_number": "US2024000001A1",
        "title": "Carbon fiber prepreg",
        "assignee": "TORAY",
        "primary_cluster_id": "bundle_prepreg",
        "total_score": 0.8,
      },
    ],
  )
  assert result["total_patents"] >= 1
  assert result["assessment_items"]
