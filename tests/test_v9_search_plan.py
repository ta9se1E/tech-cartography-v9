"""Tests for the v9 unified search plan core."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from services_v9.search_plan import (
  DEFAULT_SOURCE_LIMITS,
  DEFAULT_TOTAL_LIMIT,
  batch_terms,
  build_company_search_plan,
  build_paper_search_plan,
  build_patent_search_plan,
  build_unified_search_plan,
  build_web_search_plan,
  normalize_source_limits,
  normalize_total_limit,
  summarize_search_plan_ja,
  validate_search_plan,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEARCH_PLAN_SOURCE = (PROJECT_ROOT / "services_v9" / "search_plan.py").read_text(encoding="utf-8")


def _profile() -> dict:
  return {
    "schema_version": "v9.2",
    "theme_name": "PAN系炭素繊維前駆体の欠陥制御",
    "theme_description": "前駆体の表面欠陥と内部ボイドを監視する",
    "keywords": {
      "core_en": [
        "PAN carbon fiber precursor",
        "surface defect",
        "internal void",
        "precursor fiber",
        "microvoid",
        "porosity",
        "skin layer",
      ],
      "core_ja": [
        "PAN系炭素繊維前駆体",
        "表面欠陥",
        "内部ボイド",
        "前駆体繊維",
      ],
      "application_en": [
        "high strength carbon fiber",
        "CFRP",
        "composite reinforcement",
      ],
      "application_ja": [
        "高強度炭素繊維",
        "複合材補強",
      ],
      "material_process_en": [
        "coagulation bath",
        "dry densification",
        "wet spinning",
        "stretching",
      ],
      "material_process_ja": [
        "凝固浴",
        "乾燥緻密化",
        "湿式紡糸",
        "延伸",
      ],
      "exclude_en": ["graphene", "CNT"],
      "exclude_ja": ["汎用ニュース", "電池電極"],
    },
    "seed_publications": ["JP2022090764A", "JP2022090764A"],
    "candidate_publications": ["JP2018141251A", "jp2018141251a"],
    "target_companies": ["東レ", "帝人", "Mitsubishi Chemical", "Hexcel", "SGL"],
    "countries": ["JP", "US"],
    "source_types": ["patent", "paper", "web", "company"],
    "cadence": "weekly",
    "priority_rules": [],
    "notes": "",
  }


def _legacy_profile() -> dict:
  return {
    "theme": "legacy PAN defect watch",
    "include_keywords": ["PAN precursor", "内部ボイド", "surface defect"],
    "exclude_keywords": ["graphene", "汎用ニュース"],
    "seed_publications": ["JP2022090764A"],
    "candidate_publications": ["JP2018141251A"],
    "target_companies": ["東レ"],
  }


def test_default_total_limit_is_1000() -> None:
  assert DEFAULT_TOTAL_LIMIT == 1000


def test_default_source_limits_are_500_300_100_100() -> None:
  assert DEFAULT_SOURCE_LIMITS == {
    "patent": 500,
    "paper": 300,
    "web": 100,
    "company": 100,
  }


def test_default_source_limit_sum_is_1000() -> None:
  assert sum(DEFAULT_SOURCE_LIMITS.values()) == 1000


def test_total_limit_can_be_changed_to_500() -> None:
  assert normalize_source_limits(500) == {
    "patent": 250,
    "paper": 150,
    "web": 50,
    "company": 50,
  }


def test_ratio_70_20_5_5_converts_to_counts() -> None:
  assert normalize_source_limits(1000, {"patent": 70, "paper": 20, "web": 5, "company": 5}) == {
    "patent": 700,
    "paper": 200,
    "web": 50,
    "company": 50,
  }


def test_invalid_total_limit_becomes_1000() -> None:
  assert normalize_total_limit(None) == 1000
  assert normalize_total_limit(False) == 1000
  assert normalize_total_limit(0) == 1000


def test_total_limit_is_capped_at_5000() -> None:
  assert normalize_total_limit(99999) == 5000


def test_batch_terms_splits_every_six_terms() -> None:
  terms = [f"term_{index}" for index in range(13)]
  assert batch_terms(terms) == [
    [f"term_{index}" for index in range(6)],
    [f"term_{index}" for index in range(6, 12)],
    ["term_12"],
  ]


def test_batch_terms_removes_duplicates() -> None:
  assert batch_terms([" A ", "B", "A", "", "B", "C"]) == [["A", "B", "C"]]


def test_batch_terms_preserves_order() -> None:
  assert batch_terms(["gamma", "alpha", "beta"]) == [["gamma", "alpha", "beta"]]


def test_patent_queries_use_english_core_terms() -> None:
  plan = build_patent_search_plan(_profile(), 500)
  assert any(query["language"] == "en" for query in plan["queries"])
  assert any("PAN carbon fiber precursor" in query["query_text"] for query in plan["queries"])


def test_patent_queries_use_japanese_core_terms() -> None:
  plan = build_patent_search_plan(_profile(), 500)
  assert any(query["language"] == "ja" for query in plan["queries"])
  assert any("PAN系炭素繊維前駆体" in query["query_text"] for query in plan["queries"])


def test_patent_queries_use_material_process_terms() -> None:
  plan = build_patent_search_plan(_profile(), 500)
  assert any("coagulation bath" in query["query_text"] or "凝固浴" in query["query_text"] for query in plan["queries"])


def test_patent_queries_use_application_terms() -> None:
  plan = build_patent_search_plan(_profile(), 500)
  assert any("high strength carbon fiber" in query["query_text"] or "高強度炭素繊維" in query["query_text"] for query in plan["queries"])


def test_seed_publications_are_preserved() -> None:
  plan = build_patent_search_plan(_profile(), 500)
  assert "JP2022090764A" in plan["seed_publications"]


def test_candidate_publications_are_preserved() -> None:
  plan = build_patent_search_plan(_profile(), 500)
  assert "JP2018141251A" in plan["seed_publications"]


def test_seed_publications_are_deduplicated() -> None:
  plan = build_patent_search_plan(_profile(), 500)
  assert plan["seed_publications"].count("JP2022090764A") == 1
  assert plan["seed_publications"].count("JP2018141251A") == 1


def test_exclude_terms_are_preserved() -> None:
  plan = build_patent_search_plan(_profile(), 500)
  assert "graphene" in plan["exclude_terms"]
  assert "汎用ニュース" in plan["exclude_terms"]


def test_paper_queries_can_be_generated() -> None:
  plan = build_paper_search_plan(_profile(), 300)
  assert plan["queries"]


def test_web_queries_can_be_generated() -> None:
  plan = build_web_search_plan(_profile(), 100)
  assert plan["queries"]


def test_company_queries_can_be_generated() -> None:
  plan = build_company_search_plan(_profile(), 100)
  assert plan["queries"]


def test_company_queries_use_target_companies() -> None:
  plan = build_company_search_plan(_profile(), 100)
  joined = "\n".join(query["query_text"] for query in plan["queries"])
  assert "東レ" in joined or "Mitsubishi Chemical" in joined


def test_company_plan_without_target_companies_still_generates_queries() -> None:
  profile = _profile()
  profile["target_companies"] = []
  plan = build_company_search_plan(profile, 100)
  assert plan["queries"]
  assert plan["target_companies"] == []


def test_query_ids_are_unique() -> None:
  plan = build_unified_search_plan(_profile())
  query_ids = [
    query["query_id"]
    for source_plan in plan["plans"].values()
    for query in source_plan["queries"]
  ]
  assert len(query_ids) == len(set(query_ids))


def test_query_texts_are_not_empty() -> None:
  plan = build_unified_search_plan(_profile())
  assert all(query["query_text"].strip() for source_plan in plan["plans"].values() for query in source_plan["queries"])


def test_each_query_has_six_terms_or_less() -> None:
  plan = build_unified_search_plan(_profile())
  assert all(len(query["terms"]) <= 6 for source_plan in plan["plans"].values() for query in source_plan["queries"])


def test_patent_query_count_is_capped_at_12() -> None:
  plan = build_patent_search_plan(_profile(), 500)
  assert len(plan["queries"]) <= 12


def test_paper_query_count_is_capped_at_12() -> None:
  plan = build_paper_search_plan(_profile(), 300)
  assert len(plan["queries"]) <= 12


def test_web_query_count_is_capped_at_10() -> None:
  plan = build_web_search_plan(_profile(), 100)
  assert len(plan["queries"]) <= 10


def test_company_query_count_is_capped_at_10() -> None:
  plan = build_company_search_plan(_profile(), 100)
  assert len(plan["queries"]) <= 10


def test_unified_plan_contains_four_sources() -> None:
  plan = build_unified_search_plan(_profile())
  assert set(plan["plans"].keys()) == {"patent", "paper", "web", "company"}


def test_execution_enabled_is_false() -> None:
  plan = build_unified_search_plan(_profile())
  assert plan["execution_enabled"] is False


def test_validate_search_plan_returns_empty_for_valid_plan() -> None:
  assert validate_search_plan(build_unified_search_plan(_profile())) == []


def test_validate_search_plan_returns_japanese_errors_for_invalid_plan() -> None:
  invalid_plan = build_unified_search_plan(_profile())
  invalid_plan["execution_enabled"] = True
  invalid_plan["source_limits"]["patent"] = 0
  errors = validate_search_plan(invalid_plan)
  assert errors
  assert any("execution_enabled" in error or "一致しません" in error for error in errors)


def test_summary_contains_counts() -> None:
  summary = summarize_search_plan_ja(build_unified_search_plan(_profile()))
  assert "最大取得件数: 1000件" in summary
  assert "特許:" in summary
  assert "外部検索実行: OFF" in summary


def test_legacy_watch_profile_does_not_fail() -> None:
  plan = build_unified_search_plan(_legacy_profile())
  assert plan["plans"]["patent"]["queries"]


def test_original_watch_profile_is_not_mutated() -> None:
  profile = _profile()
  original = deepcopy(profile)
  build_unified_search_plan(profile)
  assert profile == original


def test_search_plan_code_does_not_call_external_apis() -> None:
  banned_tokens = [
    "import requests",
    "import httpx",
    "from openai",
    "google.generativeai",
    "WebSearch(",
    "CallMcpTool(",
  ]
  assert all(token not in SEARCH_PLAN_SOURCE for token in banned_tokens)
