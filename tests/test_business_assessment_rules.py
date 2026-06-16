"""Tests for business assessment rules."""

from tech_cartography.agents.business_assessment_rules import (
  classify_business_action,
  score_company_activity,
  score_design_around_opportunity,
  score_ip_watch_priority,
  score_overall_business_confidence,
  score_sme_entry_opportunity,
  score_technical_business_alignment,
  score_web_signal_strength,
)


def _business_link(**overrides) -> dict:
  base = {
    "relation": "business_signal_candidate",
    "signal_type": "production_expansion",
    "source_quality_level": "high",
    "source_title": "Capacity expansion",
  }
  base.update(overrides)
  return base


def test_web_signal_strength_increases_with_business_candidates() -> None:
  strong = score_web_signal_strength([_business_link(), _business_link(signal_type="partnership")])
  weak = score_web_signal_strength([{"relation": "weak_signal", "signal_type": "hiring"}])
  assert strong["score"] > weak["score"]
  assert strong["business_signal_count"] == 2


def test_weak_only_does_not_boost_confidence_too_much() -> None:
  scores = {
    "web_signal_strength": score_web_signal_strength([{"relation": "weak_signal", "signal_type": "hiring"}]),
    "company_activity": score_company_activity([{"relation": "weak_signal", "signal_type": "hiring"}]),
    "technical_business_alignment": score_technical_business_alignment({}, []),
    "ip_watch_priority": score_ip_watch_priority({}, {}, []),
    "sme_entry_opportunity": score_sme_entry_opportunity({}, {}, []),
    "design_around_opportunity": score_design_around_opportunity({}),
  }
  overall = score_overall_business_confidence(scores)
  assert overall["overall_confidence"] in {"low", "unknown", "medium"}


def test_technical_high_with_business_signal() -> None:
  alignment = score_technical_business_alignment(
    {"overall_technical_confidence": "high", "overall_technical_score": 0.8},
    [_business_link()],
  )
  assert alignment["score"] >= 0.5


def test_technical_low_with_business_signal_requires_review() -> None:
  alignment = score_technical_business_alignment(
    {"overall_technical_confidence": "low", "overall_technical_score": 0.2},
    [_business_link()],
  )
  assert alignment["human_review_required"]


def test_sme_surface_interface_opportunity() -> None:
  result = score_sme_entry_opportunity(
    {"primary_cluster_id": "surface_interface", "title": "surface treatment interface adhesion"},
    {},
    [],
  )
  assert result["opportunity_type"] == "sme_entry_candidate"


def test_core_manufacturing_watch_avoid() -> None:
  result = score_sme_entry_opportunity(
    {"primary_cluster_id": "core_manufacturing", "assignee": "TORAY"},
    {},
    [_business_link(), _business_link()],
  )
  assert result["opportunity_type"] in {"watch_avoid_or_partner", "verification_candidate"}


def test_design_around_with_gaps() -> None:
  result = score_design_around_opportunity(
    {"weak_or_uncertain_points": ["claim_only element"]},
    [{"gap_type": "no_paper_found"}],
    {"primary_cluster_id": "surface_interface"},
  )
  assert result["score"] >= 0.35


def test_source_quality_high_medium_boosts_score() -> None:
  high = score_web_signal_strength([_business_link(source_quality_level="high")])
  low = score_web_signal_strength([_business_link(source_quality_level="low")])
  assert high["score"] > low["score"]


def test_classify_business_action_returns_value() -> None:
  scores = {
    "web_signal_strength": score_web_signal_strength([_business_link()]),
    "company_activity": score_company_activity([_business_link()]),
    "technical_business_alignment": score_technical_business_alignment(
      {"overall_technical_confidence": "high", "overall_technical_score": 0.75},
      [_business_link()],
    ),
    "ip_watch_priority": score_ip_watch_priority({"assignee": "TORAY", "total_score": 0.8}, {"overall_technical_score": 0.7}, [_business_link()]),
    "sme_entry_opportunity": score_sme_entry_opportunity({"primary_cluster_id": "surface_interface"}, {}, []),
    "design_around_opportunity": score_design_around_opportunity({}),
  }
  scores["overall"] = score_overall_business_confidence(scores)
  action = classify_business_action(scores)
  assert action
