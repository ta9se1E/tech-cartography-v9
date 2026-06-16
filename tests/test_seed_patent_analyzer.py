"""Tests for seed patent analyzer."""

from tech_cartography.config import load_carbon_fiber_demo_profile
from tech_cartography.domain.patent_record import PatentRecord
from tech_cartography.strategy.search_strategy_builder import build_search_strategy
from tech_cartography.strategy.seed_patent_analyzer import (
  analyze_seed_patents,
  extract_seed_terms,
  sanitize_seed_terms,
)


def _sample_seed_patent() -> PatentRecord:
  return PatentRecord(
    publication_number="JP-2020-000001",
    title="PAN-based carbon fiber with improved carbonization process",
    abstract=(
      "A PAN precursor fiber is stabilized and carbonized to obtain carbon fiber "
      "with high tensile strength and modulus for aerospace composite applications."
    ),
    assignee="Toray Industries",
    claims="carbonization; stabilization; modulus; tensile strength",
    measured_properties="tensile strength 5.5 GPa; modulus 290 GPa",
    examples="Example 1: carbonization at 1200 C",
  )


def test_extract_seed_terms_from_seed_patent() -> None:
  terms = extract_seed_terms([_sample_seed_patent()])
  assert "PAN" in terms["materials"]
  assert "carbonization" in terms["processes"]
  assert "modulus" in terms["properties"]


def test_pan_not_in_exclude_terms() -> None:
  seed = PatentRecord(
    publication_number="US-0001",
    title="PAN carbon fiber battery graphene carbon nanotube",
    abstract="PAN carbon fiber process with battery and graphene noise.",
  )
  analysis = analyze_seed_patents([seed])
  assert "PAN" not in analysis["candidate_exclude_terms"]
  profile = load_carbon_fiber_demo_profile()
  strategy = build_search_strategy(profile, seed_patents=[seed])
  for plan in strategy["query_plans"]:
    lowered = [term.lower() for term in plan["exclude_terms"]]
    assert "pan" not in lowered


def test_off_topic_terms_go_to_exclude_terms() -> None:
  seed = PatentRecord(
    publication_number="US-0002",
    title="carbon fiber battery graphene carbon nanotube",
    abstract="carbon fiber with battery electrode graphene and carbon nanotube additives",
  )
  analysis = analyze_seed_patents([seed])
  lowered = [term.lower() for term in analysis["candidate_exclude_terms"]]
  assert "battery" in lowered
  assert "graphene" in lowered
  assert "carbon nanotube" in lowered


def test_precursor_warning() -> None:
  seed = PatentRecord(
    publication_number="US-0003",
    title="precursor oxidation process",
    abstract="A precursor is oxidized before treatment.",
  )
  terms = extract_seed_terms([seed])
  sanitized = sanitize_seed_terms(terms)
  assert any("precursor" in warning.lower() for warning in sanitized["warnings"])


def test_seed_terms_reflected_in_search_strategy() -> None:
  profile = load_carbon_fiber_demo_profile()
  strategy = build_search_strategy(profile, seed_patents=[_sample_seed_patent()])
  core_plan = next(
    plan for plan in strategy["query_plans"] if plan["intent_id"] == "core_manufacturing"
  )
  should_have = " ".join(core_plan["should_have_terms"]).lower()
  assert "carbonization" in should_have
  assert "modulus" in should_have
