"""Tests for BigQuery full text SQL builder."""

from tech_cartography.retrieval.bigquery_fulltext_query_builder import (
  build_publication_number_variants,
  build_us_fulltext_query,
  is_us_publication,
  normalize_us_publication_number,
)


def test_is_us_publication_variants() -> None:
  assert is_us_publication("US-2026078228A1")
  assert is_us_publication("US2026078228A1")
  assert is_us_publication("JP2020000001", country="US")
  assert not is_us_publication("JP2020000001", country="JP")
  assert not is_us_publication("EP1234567A1", country="EP")


def test_manual_route_countries() -> None:
  assert not is_us_publication("JP2020000001", country="JP")
  assert not is_us_publication("EP1234567A1", country="EP")
  assert not is_us_publication("WO2020000001", country="WO")


def test_build_us_fulltext_query_contains_fields() -> None:
  sql = build_us_fulltext_query("US-2026078228A1")
  assert "claims_localized" in sql
  assert "description_localized" in sql
  assert "publication_number" in sql
  assert "US-2026078228A1" in sql or "US2026078228A1" in sql


def test_publication_number_variants() -> None:
  variants = build_publication_number_variants("US-2026078228A1")
  assert "US2026078228A1" in variants
  assert normalize_us_publication_number("US-12590616B2") == "US12590616B2"


def test_us_12565719_b2_variants() -> None:
  variants = build_publication_number_variants("US-12565719-B2")
  assert "US12565719B2" in variants or "US-12565719B2" in variants


def test_non_us_sql_not_built() -> None:
  from tech_cartography.retrieval.bigquery_fulltext_query_builder import validate_us_fulltext_request

  result = validate_us_fulltext_request("CN-121137864-A", "CN")
  assert not result["ok"]
  try:
    build_us_fulltext_query("CN-121137864-A", country="CN")
    raised = False
  except ValueError:
    raised = True
  assert raised
