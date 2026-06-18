"""Tests for Web Signal query templates (Phase 23.1)."""

from __future__ import annotations

from tech_cartography.web_signals.query_templates import (
  TECHNOLOGY_TERMS,
  build_web_signal_queries,
)


def test_technology_terms_present() -> None:
  assert "PAN carbon fiber" in TECHNOLOGY_TERMS
  assert "hydrogen tank" in TECHNOLOGY_TERMS


def test_national_project_queries_built() -> None:
  queries = build_web_signal_queries(
    "PAN carbon fiber mid-temperature carbonization",
    ["national_project", "money"],
    ["en", "ja"],
  )
  categories = {query.category for query in queries}
  assert "national_project" in categories or "money" in categories
  texts = " ".join(query.query for query in queries)
  assert "NEDO" in texts or "JST" in texts or "炭素繊維" in texts


def test_ir_disclosure_queries_built() -> None:
  queries = build_web_signal_queries(
    "PAN carbon fiber",
    ["ir_disclosure"],
    ["en", "ja"],
  )
  assert queries
  joined = " ".join(query.query for query in queries).lower()
  assert "investor relations" in joined or "決算" in joined or "ir" in joined
  assert all(query.intended_signal_type == "ir_disclosure" for query in queries)


def test_local_news_queries_built() -> None:
  queries = build_web_signal_queries("PAN carbon fiber", ["local_news"], ["ja"])
  assert queries
  joined = " ".join(query.query for query in queries)
  assert "地方" in joined or "自治体" in joined or "地元" in joined


def test_human_queries_built() -> None:
  queries = build_web_signal_queries("PAN carbon fiber", ["human"], ["en", "ja"])
  assert queries
  joined = " ".join(query.query for query in queries).lower()
  assert "job" in joined or "researcher" in joined or "求人" in joined or "研究者" in joined


def test_max_categories_respect_aliases() -> None:
  queries = build_web_signal_queries("topic", ["grant", "disclosure"], ["en"])
  categories = {query.category for query in queries}
  assert "money" in categories or "ir_disclosure" in categories
