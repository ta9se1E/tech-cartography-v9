"""Tests for Search Strategy Builder."""

from tech_cartography.config import load_carbon_fiber_demo_profile
from tech_cartography.domain.search_profile import SearchProfile
from tech_cartography.strategy.search_strategy_builder import (
  build_search_strategy,
  choose_recommended_plan,
  validate_search_strategy,
)
from tech_cartography.strategy.query_plan import QueryPlan


def test_search_profile_from_dict() -> None:
  profile = SearchProfile.from_dict(
    {
      "theme": "PAN carbon fiber",
      "materials": ["PAN", "carbon fiber"],
      "processes": ["carbonization"],
      "properties": ["modulus"],
      "applications": ["aerospace"],
      "companies": ["TORAY"],
      "countries": ["JP"],
      "exclude_terms": ["battery"],
      "year_min": 2015,
      "year_max": 2025,
    },
  )
  assert profile.theme == "PAN carbon fiber"
  assert "PAN" in profile.normalized_terms()["materials"]


def test_load_carbon_fiber_demo_profile() -> None:
  profile = load_carbon_fiber_demo_profile()
  assert "carbon fiber" in profile.materials
  assert profile.year_min == 2010


def test_build_search_strategy_returns_query_plans() -> None:
  profile = load_carbon_fiber_demo_profile()
  strategy = build_search_strategy(profile)
  assert strategy["query_plans"]
  assert strategy["recommended_first_plan"] in {
    "core_manufacturing",
    "focused_carbon_fiber_process",
  }


def test_query_plans_include_required_intents() -> None:
  profile = load_carbon_fiber_demo_profile()
  strategy = build_search_strategy(profile)
  intent_ids = {plan["intent_id"] for plan in strategy["query_plans"]}
  assert "core_manufacturing" in intent_ids
  assert "surface_interface" in intent_ids
  assert "bundle_prepreg" in intent_ids
  assert "application" in intent_ids
  assert "company_watch" in intent_ids


def test_recommended_first_plan_prefers_core_manufacturing() -> None:
  profile = load_carbon_fiber_demo_profile()
  strategy = build_search_strategy(profile)
  assert strategy["recommended_first_plan"] == "core_manufacturing"
  plans = [QueryPlan.from_dict(item) for item in strategy["query_plans"]]
  assert choose_recommended_plan(plans) == "core_manufacturing"


def test_validate_search_strategy_ready() -> None:
  profile = load_carbon_fiber_demo_profile()
  strategy = build_search_strategy(profile)
  validation = validate_search_strategy(strategy)
  assert validation["status"] == "ready"
  assert strategy["status"] == "ready"
