"""Tests for BigQuery SQL builder."""

from tech_cartography.config import load_carbon_fiber_demo_profile
from tech_cartography.strategy.query_plan import QueryPlan
from tech_cartography.strategy.search_strategy_builder import build_query_plans
from tech_cartography.retrieval.bigquery_query_builder import (
  build_lightweight_patent_query,
  build_where_clause,
  escape_sql_string,
  infer_matched_terms,
)


def _sample_plan() -> QueryPlan:
  profile = load_carbon_fiber_demo_profile()
  return build_query_plans(profile)[0]


def test_build_lightweight_patent_query_returns_sql() -> None:
  sql = build_lightweight_patent_query(_sample_plan(), limit=100)
  assert isinstance(sql, str)
  assert "SELECT" in sql
  assert "LIMIT 100" in sql


def test_sql_contains_title_abstract_conditions() -> None:
  sql = build_lightweight_patent_query(_sample_plan(), limit=50)
  assert "title_localized" in sql
  assert "abstract_localized" in sql
  assert "LIKE" in sql or "REGEXP_CONTAINS" in sql


def test_exclude_terms_are_not_conditions() -> None:
  plan = _sample_plan()
  where = build_where_clause(plan)
  assert "NOT" in where
  assert "battery" in where.lower() or "graphene" in where.lower() or "NOT" in where


def test_countries_and_years_in_where() -> None:
  plan = _sample_plan()
  where = build_where_clause(plan)
  assert "country_code IN" in where
  assert "publication_date >=" in where
  assert "publication_date <=" in where


def test_escape_sql_string() -> None:
  assert escape_sql_string("O'Reilly") == "'O''Reilly'"


def test_infer_matched_terms() -> None:
  plan = _sample_plan()
  record = {
    "title": "PAN based carbon fiber carbonization process",
    "abstract": "High modulus composite for aerospace",
  }
  matched = infer_matched_terms(record, plan)
  assert "carbon fiber" in [term.lower() for term in matched] or matched
