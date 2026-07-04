"""Tests for v9 Global Web / company retrieval."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from services_v9.search_plan import build_unified_search_plan
from services_v9.web_company_retrieval import (
  build_global_web_retrieval_preview,
  execute_global_web_retrieval,
  save_global_web_retrieval_artifacts,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = (PROJECT_ROOT / "services_v9" / "web_company_retrieval.py").read_text(encoding="utf-8")
TABS_SOURCE = (PROJECT_ROOT / "ui_v9" / "tabs.py").read_text(encoding="utf-8")
APP_SOURCE = (PROJECT_ROOT / "ui_v9" / "signal_watch_app.py").read_text(encoding="utf-8")


def _profile() -> dict[str, object]:
  return {
    "theme_name": "Battery materials",
    "theme_description": "Monitor battery material R&D and investment signals.",
    "keywords": {
      "core_en": ["solid state battery", "cathode"],
      "core_ja": ["全固体電池", "正極材"],
      "application_en": ["energy density", "cycle life"],
      "application_ja": ["高エネルギー密度"],
      "material_process_en": ["electrolyte", "sintering"],
      "material_process_ja": ["電解質", "焼結"],
      "exclude_en": ["review"],
      "exclude_ja": [],
    },
    "seed_publications": [],
    "candidate_publications": [],
    "target_companies": ["Toyota"],
  }


def _custom_preview() -> dict[str, object]:
  return {
    "request": {
      "queries": [
        {
          "query_id": "gw_q001",
          "country_region_code": "JP",
          "web_intent": "research_development",
          "result_bucket": "web",
          "priority": "high",
          "query_local": "全固体電池 研究開発",
          "query_english_fallback": "solid state battery research development",
          "english_fallback_enabled": True,
          "fallback_execution_mode": "result_shortage_only",
          "max_results": 3,
          "official_source_priority": True,
          "preferred_domains": ["example.co.jp"],
          "excluded_domains": ["linkedin.com"],
        },
        {
          "query_id": "gw_q002",
          "country_region_code": "US",
          "web_intent": "investment_production",
          "result_bucket": "company",
          "priority": "high",
          "query_local": "battery factory investment",
          "query_english_fallback": "",
          "english_fallback_enabled": False,
          "fallback_execution_mode": "not_applicable",
          "max_results": 2,
          "official_source_priority": False,
          "preferred_domains": [],
          "excluded_domains": [],
        },
      ],
      "verification_limit": 2,
      "summary_top_n": 1,
      "target_companies": ["Toyota"],
      "record_stage": "staged",
      "retrieval_mode": "real",
      "execution_enabled": True,
    },
    "validation_rows": [{"status": "ok", "message": "validation passed"}],
  }


def test_preview_selects_enabled_global_web_queries() -> None:
  plan = build_unified_search_plan(_profile())
  preview = build_global_web_retrieval_preview(plan, max_query_count=3, verification_limit=10, summary_top_n=2)
  assert preview["query_count"] == 3
  assert len(preview["selected_query_ids"]) == 3
  assert preview["validation_rows"] == [{"status": "ok", "message": "validation passed"}]


def test_execute_uses_english_fallback_when_results_short() -> None:
  preview = _custom_preview()

  def _fake_tavily_post(**kwargs):
    if kwargs["url"].endswith("/search"):
      query = kwargs["payload"]["query"]
      if query == "全固体電池 研究開発":
        return {
          "results": [
            {
              "title": "Toyota 全固体電池 研究開発",
              "url": "https://example.co.jp/news/a?utm_source=test",
              "content": "研究開発の更新",
              "score": 0.9,
            },
          ],
        }
      if query == "solid state battery research development":
        return {
          "results": [
            {
              "title": "Toyota solid state battery R&D update",
              "url": "https://example.com/news/b",
              "content": "R&D update in English",
              "score": 0.7,
            },
          ],
        }
      return {"results": []}
    return {
      "results": [
        {
          "url": kwargs["payload"]["urls"][0],
          "raw_content": "A" * 700,
        },
      ],
    }

  result = execute_global_web_retrieval(dict(preview), tavily_search_post_fn=_fake_tavily_post, tavily_extract_post_fn=_fake_tavily_post, sleeper=lambda _s: None)
  assert result["provider_status"] in {"success", "partial_success"}
  assert result["rows_retrieved"] >= 2
  assert any(log.get("variant") == "english_fallback" for log in result["provider_log"] if log.get("stage") == "discovery")
  first = result["rows"][0]
  assert first["canonical_url"].startswith("https://")
  assert first["content_hash"]
  assert first["same_story_group"].startswith("story_")


def test_execute_keeps_partial_success_when_one_query_fails() -> None:
  preview = _custom_preview()

  def _fake_tavily_post(**kwargs):
    if kwargs["url"].endswith("/search"):
      query = kwargs["payload"]["query"]
      if query == "battery factory investment":
        return {"error": "http_500"}
      return {
        "results": [
          {
            "title": "Toyota 全固体電池 研究開発",
            "url": "https://example.co.jp/news/a",
            "content": "研究開発の更新",
            "score": 0.9,
          },
        ],
      }
    return {"results": [{"url": kwargs["payload"]["urls"][0], "raw_content": "B" * 700}]}

  result = execute_global_web_retrieval(dict(preview), tavily_search_post_fn=_fake_tavily_post, tavily_extract_post_fn=_fake_tavily_post, sleeper=lambda _s: None)
  assert result["provider_status"] == "partial_success"
  assert result["rows_retrieved"] >= 1
  assert result["error"] is not None


def test_verification_uses_google_grounding_fallback_when_extract_unavailable() -> None:
  preview = _custom_preview()

  def _fake_tavily_post(**kwargs):
    if kwargs["url"].endswith("/search"):
      return {
        "results": [
          {
            "title": "Toyota factory investment",
            "url": "https://company.example.com/pr/factory",
            "content": "Factory investment update",
            "score": 0.8,
          },
        ],
      }
    return {"results": [{"url": kwargs["payload"]["urls"][0], "raw_content": ""}]}

  def _fake_grounding(target: dict[str, object]) -> dict[str, object]:
    assert target["source_url"] == "https://company.example.com/pr/factory"
    return {
      "summary_ja": "工場投資に関する候補。原典確認が必要です。",
      "content_access": "partial",
      "official_hint": "company_official",
    }

  result = execute_global_web_retrieval(
    dict(preview),
    tavily_search_post_fn=_fake_tavily_post,
    tavily_extract_post_fn=_fake_tavily_post,
    google_grounding_fn=_fake_grounding,
    sleeper=lambda _s: None,
  )
  assert result["rows_retrieved"] >= 1
  row = result["rows"][0]
  assert row["content_access"] == "partial"
  assert "google_search_grounding" in row["verification_provider"]
  assert row["summary_ja"]


def test_artifacts_are_saved_for_web_company_retrieval(tmp_path: Path) -> None:
  preview = _custom_preview()
  result = {
    "retrieval_run_id": "web_company_retrieval_20260704_132500",
    "provider_status": "success",
    "rows": [
      {
        "candidate_id": "wcc_1",
        "query_id": "gw_q001",
        "country_region": "JP",
        "web_intent": "research_development",
        "result_bucket": "web",
        "original_title": "Toyota 全固体電池 研究開発",
        "original_snippet": "研究開発の更新",
        "original_language": "ja",
        "source_url": "https://example.co.jp/news/a",
        "canonical_url": "https://example.co.jp/news/a",
        "event_type": "research_development",
        "organization": "Toyota",
        "source_quality": "medium_high",
        "content_access": "full",
        "content_hash": "abc",
        "same_story_group": "story_001",
        "summary_ja": "Toyota / JP / research_development: 研究開発更新",
        "retrieval_run_id": "web_company_retrieval_20260704_132500",
        "provider_status": "success",
        "record_stage": "staged",
        "retrieval_mode": "real",
      },
    ],
    "discovery_rows": [{"query_id": "gw_q001"}],
    "verification_rows": [{"candidate_id": "wcc_1"}],
    "provider_log": [{"stage": "discovery"}],
    "error": None,
  }
  paths = save_global_web_retrieval_artifacts(dict(preview), result, base_dir=tmp_path / "v9_runs")
  assert paths["plan_json"].exists()
  assert paths["discovery_json"].exists()
  assert paths["verification_json"].exists()
  assert paths["staged_json"].exists()
  assert paths["staged_csv"].exists()
  assert paths["provider_log_json"].exists()


def test_ui_source_contains_global_web_controls() -> None:
  required = [
    "Global Web / Company Retrieval",
    "Global Web / 企業情報取得を実行",
    "Global Web実行query上限",
    "Verification対象上限",
    "Google Search Grounding",
  ]
  assert all(label in TABS_SOURCE for label in required)
  assert "run_global_web_retrieval" in APP_SOURCE


def test_source_code_avoids_full_bulk_translation() -> None:
  assert "全件翻訳" not in SOURCE
  assert "google scholar" not in SOURCE.lower()


def test_streamlit_testing_finds_global_web_controls() -> None:
  at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
  at.run()
  button_labels = [button.label for button in at.button]
  assert "Global Web / 企業情報取得を実行" in button_labels
