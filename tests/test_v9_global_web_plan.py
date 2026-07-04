"""Tests for the v9 global web search plan backend."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from services_v9.global_web_plan import (
  build_global_web_country_coverage,
  build_global_web_plan_validation_rows,
  build_global_web_search_plan,
  summarize_global_web_search_plan_ja,
  validate_global_web_search_plan,
)
from services_v9.global_web_plan_export import export_global_web_search_plan
from services_v9.global_web_plan_schema import (
  DEFAULT_GLOBAL_WEB_COUNTRY_CODES,
  DEFAULT_GLOBAL_WEB_INTENTS,
  GLOBAL_WEB_PLAN_SCHEMA_VERSION,
  load_global_web_country_profiles,
  validate_country_profiles,
)
from services_v9.search_plan import build_unified_search_plan

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GLOBAL_WEB_PLAN_SOURCE = (PROJECT_ROOT / "services_v9" / "global_web_plan.py").read_text(encoding="utf-8")
SEARCH_PLAN_SOURCE = (PROJECT_ROOT / "services_v9" / "search_plan.py").read_text(encoding="utf-8")


def _profile() -> dict:
  return {
    "schema_version": "v9.2",
    "theme_name": "PAN系炭素繊維前駆体の欠陥制御",
    "theme_description": "前駆体の表面欠陥と内部ボイドを監視する",
    "keywords": {
      "core_en": ["PAN carbon fiber precursor", "surface defect", "internal void"],
      "core_ja": ["PAN系炭素繊維前駆体", "表面欠陥", "内部ボイド"],
      "application_en": ["high strength carbon fiber", "CFRP"],
      "application_ja": ["高強度炭素繊維", "複合材補強"],
      "material_process_en": ["coagulation bath", "dry densification"],
      "material_process_ja": ["凝固浴", "乾燥緻密化"],
      "exclude_en": ["graphene"],
      "exclude_ja": ["汎用ニュース"],
    },
    "seed_publications": ["JP2022090764A"],
    "candidate_publications": ["JP2018141251A"],
    "target_companies": ["東レ", "帝人", "Mitsubishi Chemical", "Hexcel", "SGL", "Solvay"],
    "source_types": ["patent", "paper", "web", "company"],
  }


def test_country_profiles_cover_ten_country_regions() -> None:
  profiles = load_global_web_country_profiles()
  assert [profile["country_region_code"] for profile in profiles] == list(DEFAULT_GLOBAL_WEB_COUNTRY_CODES)


def test_country_profiles_validate_cleanly() -> None:
  assert validate_country_profiles(load_global_web_country_profiles()) == []


def test_global_web_plan_schema_version_is_set() -> None:
  plan = build_global_web_search_plan(_profile(), 100, 100)
  assert plan["schema_version"] == GLOBAL_WEB_PLAN_SCHEMA_VERSION


def test_global_web_plan_execution_enabled_is_false() -> None:
  plan = build_global_web_search_plan(_profile(), 100, 100)
  assert plan["execution_enabled"] is False


def test_global_web_plan_contains_all_intents() -> None:
  plan = build_global_web_search_plan(_profile(), 100, 100)
  assert plan["intents"] == list(DEFAULT_GLOBAL_WEB_INTENTS)


def test_global_web_plan_generates_queries_for_all_countries_and_intents() -> None:
  plan = build_global_web_search_plan(_profile(), 100, 100)
  assert len(plan["queries"]) == len(DEFAULT_GLOBAL_WEB_COUNTRY_CODES) * len(DEFAULT_GLOBAL_WEB_INTENTS)


def test_high_priority_queries_are_enabled_and_around_thirty() -> None:
  plan = build_global_web_search_plan(_profile(), 100, 100)
  enabled_queries = [query for query in plan["queries"] if query["enabled"]]
  assert len(enabled_queries) == 30
  assert all(query["priority"] == "high" for query in enabled_queries)


def test_medium_and_low_priority_queries_start_disabled() -> None:
  plan = build_global_web_search_plan(_profile(), 100, 100)
  assert all(not query["enabled"] for query in plan["queries"] if query["priority"] in {"medium", "low"})


def test_jp_uses_japanese_local_query() -> None:
  plan = build_global_web_search_plan(_profile(), 100, 100)
  jp_query = next(query for query in plan["queries"] if query["country_region_code"] == "JP" and query["web_intent"] == "research_development")
  assert "PAN系炭素繊維前駆体" in jp_query["query_local"]
  assert "研究開発" in jp_query["query_local"]


def test_english_market_uses_english_query() -> None:
  plan = build_global_web_search_plan(_profile(), 100, 100)
  us_query = next(query for query in plan["queries"] if query["country_region_code"] == "US" and query["web_intent"] == "research_development")
  assert "PAN carbon fiber precursor" in us_query["query_local"]
  assert "research development" in us_query["query_local"]
  assert us_query["query_english_fallback"] == ""


def test_non_english_market_can_use_translation_pending_mode() -> None:
  plan = build_global_web_search_plan(_profile(), 100, 100)
  de_query = next(query for query in plan["queries"] if query["country_region_code"] == "DE" and query["web_intent"] == "research_development")
  assert de_query["local_query_generation_mode"] == "translation_pending"
  assert de_query["query_english_fallback"]


def test_result_bucket_is_web_or_company() -> None:
  plan = build_global_web_search_plan(_profile(), 100, 100)
  assert {query["result_bucket"] for query in plan["queries"]} == {"web", "company"}


def test_web_and_company_budget_stay_within_limits_for_enabled_queries() -> None:
  plan = build_global_web_search_plan(_profile(), 100, 100)
  enabled_web = sum(query["max_results"] for query in plan["queries"] if query["enabled"] and query["result_bucket"] == "web")
  enabled_company = sum(query["max_results"] for query in plan["queries"] if query["enabled"] and query["result_bucket"] == "company")
  assert enabled_web <= 100
  assert enabled_company <= 100
  assert enabled_web == 100
  assert enabled_company == 100


def test_provider_routing_fields_are_present() -> None:
  query = build_global_web_search_plan(_profile(), 100, 100)["queries"][0]
  assert query["provider_primary"]
  assert "provider_fallback" in query
  assert query["verification_provider"]


def test_company_bucket_queries_can_include_target_company_anchor() -> None:
  plan = build_global_web_search_plan(_profile(), 100, 100)
  company_query = next(query for query in plan["queries"] if query["web_intent"] == "investment_production" and query["country_region_code"] == "JP")
  assert "東レ" in company_query["query_local"]


def test_exclude_terms_are_carried_into_global_queries() -> None:
  query = build_global_web_search_plan(_profile(), 100, 100)["queries"][0]
  assert "graphene" in query["exclude_terms"]
  assert "汎用ニュース" in query["exclude_terms"]


def test_dedupe_key_is_present_and_query_ids_are_unique() -> None:
  plan = build_global_web_search_plan(_profile(), 100, 100)
  query_ids = [query["query_id"] for query in plan["queries"]]
  assert len(query_ids) == len(set(query_ids))
  assert all(query["dedupe_key"] for query in plan["queries"])


def test_country_coverage_rows_are_generated() -> None:
  coverage = build_global_web_country_coverage(build_global_web_search_plan(_profile(), 100, 100))
  assert len(coverage) == 10
  assert coverage[0]["country_region_code"] == "JP"


def test_validation_passes_for_valid_plan() -> None:
  assert validate_global_web_search_plan(build_global_web_search_plan(_profile(), 100, 100)) == []


def test_validation_rows_report_ok_for_valid_plan() -> None:
  rows = build_global_web_plan_validation_rows(build_global_web_search_plan(_profile(), 100, 100))
  assert rows == [{"status": "ok", "message": "validation passed"}]


def test_invalid_plan_returns_japanese_errors() -> None:
  invalid = build_global_web_search_plan(_profile(), 100, 100)
  invalid["execution_enabled"] = True
  errors = validate_global_web_search_plan(invalid)
  assert errors
  assert any("execution_enabled" in error for error in errors)


def test_summary_mentions_budget_and_enabled_queries() -> None:
  summary = summarize_global_web_search_plan_ja(build_global_web_search_plan(_profile(), 100, 100))
  assert "Global Web検索計画" in summary
  assert "Web予算: 100件" in summary
  assert "初期有効クエリ数: 30" in summary


def test_export_creates_required_artifacts(tmp_path: Path) -> None:
  plan = build_global_web_search_plan(_profile(), 100, 100)
  paths = export_global_web_search_plan(plan, tmp_path)
  assert set(paths.keys()) == {"csv", "json", "markdown", "country_coverage_csv", "validation_csv"}
  assert all(path.exists() for path in paths.values())
  assert paths["csv"].name == "global_web_search_plan.csv"
  assert paths["json"].name == "global_web_search_plan.json"
  assert paths["markdown"].name == "global_web_search_plan.md"
  assert paths["country_coverage_csv"].name == "global_web_country_coverage.csv"
  assert paths["validation_csv"].name == "global_web_search_plan_validation.csv"


def test_exported_json_contains_queries_and_country_metadata(tmp_path: Path) -> None:
  plan = build_global_web_search_plan(_profile(), 100, 100)
  paths = export_global_web_search_plan(plan, tmp_path)
  payload = json.loads(paths["json"].read_text(encoding="utf-8"))
  assert len(payload["queries"]) == 60
  assert len(payload["countries"]) == 10


def test_exported_csv_contains_required_headers(tmp_path: Path) -> None:
  plan = build_global_web_search_plan(_profile(), 100, 100)
  paths = export_global_web_search_plan(plan, tmp_path)
  header = paths["csv"].read_text(encoding="utf-8").splitlines()[0]
  assert "query_id" in header
  assert "country_region_code" in header
  assert "provider_primary" in header


def test_exported_validation_csv_contains_ok_row(tmp_path: Path) -> None:
  plan = build_global_web_search_plan(_profile(), 100, 100)
  paths = export_global_web_search_plan(plan, tmp_path)
  text = paths["validation_csv"].read_text(encoding="utf-8")
  assert "ok" in text
  assert "validation passed" in text


def test_unified_search_plan_includes_global_web_plan() -> None:
  plan = build_unified_search_plan(_profile())
  assert "global_web_plan" in plan
  assert plan["global_web_plan"]["web_limit"] == 100
  assert plan["global_web_plan"]["company_limit"] == 100


def test_original_profile_is_not_mutated() -> None:
  profile = _profile()
  original = deepcopy(profile)
  build_global_web_search_plan(profile, 100, 100)
  assert profile == original


def test_global_web_plan_code_does_not_call_external_apis() -> None:
  banned_tokens = [
    "import requests",
    "import httpx",
    "from openai",
    "google.generativeai",
    "WebSearch(",
    "CallMcpTool(",
    "Tavily",
    "translate(",
  ]
  combined_source = GLOBAL_WEB_PLAN_SOURCE + "\n" + SEARCH_PLAN_SOURCE
  assert all(token not in combined_source for token in banned_tokens)
