"""Tests for synthesis rules."""

from tech_cartography.agents.synthesis_rules import (
  assign_synthesis_importance,
  build_global_caveats,
  select_priority_patents,
  synthesize_sme_action_plan,
)


def _patent(pub: str, rank: int, **overrides) -> dict:
  base = {
    "publication_number": pub,
    "title": f"Patent {pub}",
    "assignee": "TORAY",
    "primary_cluster_id": "bundle_prepreg",
    "rank": rank,
    "noise_score": 0.0,
  }
  base.update(overrides)
  return base


def test_priority_patents_favor_high_technical_and_business() -> None:
  top20 = [_patent("US1", 1), _patent("US2", 10)]
  technical = [
    {"publication_number": "US1", "overall_technical_confidence": "high", "strongest_supported_points": ["paper candidate"]},
    {"publication_number": "US2", "overall_technical_confidence": "low"},
  ]
  business = [
    {"publication_number": "US1", "overall_business_confidence": "high", "recommended_reader_action": "monitor_company_signals"},
    {"publication_number": "US2", "overall_business_confidence": "low"},
  ]
  priority = select_priority_patents(top20, technical, business)
  assert priority[0]["publication_number"] == "US1"
  assert priority[0]["priority_score"] > priority[1]["priority_score"]


def test_human_review_when_many_gaps() -> None:
  top20 = [_patent("US1", 2)]
  technical = [{"publication_number": "US1", "overall_technical_confidence": "medium"}]
  business = [{"publication_number": "US1", "overall_business_confidence": "medium"}]
  gaps = [
    {"publication_number": "US1", "gap_type": "no_paper_found"},
    {"publication_number": "US1", "gap_type": "weak_only"},
    {"publication_number": "US1", "gap_type": "background_only"},
  ]
  priority = select_priority_patents(top20, technical, business, evidence_gaps=gaps)
  assert priority[0]["human_review_required"]


def test_sme_action_plan_categories() -> None:
  priority = [
    {
      "publication_number": "US1",
      "title": "Carbon fiber",
      "why_read": "rank 1",
      "next_check": "read_patent_and_examples_first",
      "human_review_required": False,
    },
  ]
  business = [
    {
      "publication_number": "US1",
      "recommended_reader_action": "investigate_design_around",
      "sme_opportunity_points": ["surface candidate"],
      "design_around_or_differentiation_hints": ["claim scope uncertainty"],
    },
  ]
  technical = [
    {
      "publication_number": "US1",
      "patent_title": "Carbon fiber",
      "strongest_supported_points": ["interface adhesion"],
      "key_evidence_gaps": ["no paper for element e1"],
    },
  ]
  plan = synthesize_sme_action_plan(priority, business, technical, business_assessments=business)
  categories = {section["action_category"] for section in plan}
  assert "今すぐ読むべき特許" in categories
  assert "論文で裏取りすべき技術要素" in categories
  assert "回避設計・差別化候補" in categories


def test_global_caveats_include_fto_disclaimer() -> None:
  caveats = build_global_caveats()
  assert any("FTO" in caveat for caveat in caveats)
  assert any("有効性" in caveat for caveat in caveats)


def test_assign_importance_high_for_human_review() -> None:
  assert assign_synthesis_importance({"human_review_required": True, "priority_score": 0.3}) == "high"
