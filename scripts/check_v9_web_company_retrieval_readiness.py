"""Readiness checks for v9 Global Web / company retrieval."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from streamlit.testing.v1 import AppTest

from services_v9.search_plan import build_unified_search_plan
from services_v9.web_company_retrieval import (
  build_global_web_retrieval_preview,
  execute_global_web_retrieval,
  save_global_web_retrieval_artifacts,
)


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


def main() -> int:
  errors: list[str] = []

  plan = build_unified_search_plan(_profile())
  preview = build_global_web_retrieval_preview(plan, max_query_count=3, verification_limit=10, summary_top_n=2)
  if preview["query_count"] != 3:
    errors.append("Global Web preview で query cap を反映できていません")
  if preview["validation_rows"] != [{"status": "ok", "message": "validation passed"}]:
    errors.append("Global Web preview validation が通りません")

  custom_preview = _custom_preview()

  def _fake_tavily_post(**kwargs):
    if kwargs["url"].endswith("/search"):
      query = kwargs["payload"]["query"]
      if query == "battery factory investment":
        return {"error": "http_500"}
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
    return {"results": [{"url": kwargs["payload"]["urls"][0], "raw_content": ""}]}

  def _fake_grounding(_target: dict[str, object]) -> dict[str, object]:
    return {
      "summary_ja": "候補記事です。原典確認が必要です。",
      "content_access": "partial",
      "official_hint": "company_official",
    }

  result = execute_global_web_retrieval(
    dict(custom_preview),
    tavily_search_post_fn=_fake_tavily_post,
    tavily_extract_post_fn=_fake_tavily_post,
    google_grounding_fn=_fake_grounding,
    sleeper=lambda _s: None,
  )
  if result["provider_status"] != "partial_success":
    errors.append("provider failure を partial success として保持できていません")
  if result["rows_retrieved"] < 1:
    errors.append("Global Web retrieval で候補を取得できていません")
  if not any("google_search_grounding" in str(row.get("verification_provider", "")) for row in result["rows"]):
    errors.append("Google Search Grounding fallback を反映できていません")
  if not any(str(log.get("variant", "")) == "english_fallback" for log in result["provider_log"] if log.get("stage") == "discovery"):
    errors.append("条件付き English fallback を記録できていません")

  with tempfile.TemporaryDirectory() as tmp_dir_name:
    paths = save_global_web_retrieval_artifacts(
      dict(custom_preview),
      result,
      base_dir=Path(tmp_dir_name) / "v9_runs",
    )
    if not paths["staged_json"].exists() or not paths["provider_log_json"].exists():
      errors.append("Global Web retrieval artifact 保存に失敗しました")

  tabs_source = (PROJECT_ROOT / "ui_v9" / "tabs.py").read_text(encoding="utf-8")
  required_labels = [
    "Global Web / Company Retrieval",
    "Global Web / 企業情報取得を実行",
    "Global Web実行query上限",
    "Verification対象上限",
  ]
  if not all(label in tabs_source for label in required_labels):
    errors.append("情報源タブの Global Web retrieval UI が不足しています")

  at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
  at.run()
  button_labels = [button.label for button in at.button]
  if "Global Web / 企業情報取得を実行" not in button_labels:
    errors.append("Streamlit UI で Global Web execute ボタンを検出できません")

  if errors:
    for message in errors:
      print(f"[v9 web company retrieval readiness] ERROR: {message}")
    return 1
  print("[v9 web company retrieval readiness] OK: Global Web / company retrieval is ready.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
