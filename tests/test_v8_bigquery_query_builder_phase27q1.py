"""Phase27Q.1 BigQuery SQL builder tests."""

from __future__ import annotations

from tech_cartography.runtime.v8_research_theme_schema import ResearchThemeProfile
from tech_cartography.services.v8_bigquery_query_builder import build_bigquery_query
from tech_cartography.services.v8_research_theme_defaults import FIRST_TEST_SEED_PUBLICATIONS


def _test_profile() -> ResearchThemeProfile:
  return ResearchThemeProfile(
    case_id="case_01_pan_graphitization",
    theme_name="test theme",
    core_keywords=["PAN carbon fiber precursor", "surface defect"],
    application_keywords=["CFRP"],
    material_process_keywords=["spinning dope temperature"],
    exclude_keywords=["carbon nanotube"],
    seed_publication_numbers=list(FIRST_TEST_SEED_PUBLICATIONS),
    max_results=1000,
    countries=["JP", "CN"],
    search_mode="seed_and_keywords",
  )


def test_generated_sql_contains_seeds() -> None:
  sql, cfg = build_bigquery_query(_test_profile())
  assert "JP2022090764A" in sql
  assert "JP2023163084A" in sql
  assert "JP2018084002A" in sql
  assert cfg["seed_publication_numbers"]


def test_generated_sql_contains_keywords() -> None:
  sql, _ = build_bigquery_query(_test_profile())
  assert "surface defect" in sql.lower() or "PAN carbon fiber precursor".lower() in sql.lower()
  assert "carbon nanotube" in sql.lower()


def test_limit_capped_at_1000() -> None:
  profile = _test_profile()
  profile.max_results = 5000
  profile = ResearchThemeProfile.from_dict(profile.to_dict())
  sql, cfg = build_bigquery_query(profile)
  assert "LIMIT 1000" in sql
  assert cfg["limit"] <= 1000


def test_no_jp_cn_claims_required() -> None:
  sql, cfg = build_bigquery_query(_test_profile())
  assert "no jp/cn claims" in sql.lower()
  assert cfg.get("no_claims_for_jp_cn") is True
  select_block = sql.lower().split("from base")[0] if "from base" in sql.lower() else sql.lower()
  assert "claim_text" not in select_block
  assert "description" not in select_block.split("abstract")[0] or "claim/description" in sql.lower()


def test_keyword_only_without_seed() -> None:
  profile = ResearchThemeProfile(
    case_id="case_01",
    core_keywords=["PAN"],
    search_mode="keyword_only",
    seed_publication_numbers=[],
  )
  sql, cfg = build_bigquery_query(profile)
  assert cfg["search_mode"] == "keyword_only"
  assert "LIMIT" in sql
