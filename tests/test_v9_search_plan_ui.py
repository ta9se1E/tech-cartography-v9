"""Tests for v9 search plan UI wiring."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from streamlit.testing.v1 import AppTest

from ui_v9.signal_watch_app import (
  _build_search_plan_view,
  _default_search_plan_settings,
  _normalize_manual_query,
  _stable_payload_signature,
)
from ui_v9.tabs import V9_TAB_LABELS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABS_SOURCE = (PROJECT_ROOT / "ui_v9" / "tabs.py").read_text(encoding="utf-8")
APP_SOURCE = (PROJECT_ROOT / "ui_v9" / "signal_watch_app.py").read_text(encoding="utf-8")


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
    "target_companies": ["東レ", "帝人"],
    "countries": ["JP", "US"],
    "source_types": ["patent", "paper", "web", "company"],
    "cadence": "weekly",
    "priority_rules": [],
    "notes": "",
  }


def test_tab_count_remains_six() -> None:
  assert len(V9_TAB_LABELS) == 6


def test_profile_signature_changes_when_profile_changes() -> None:
  profile_a = _profile()
  profile_b = deepcopy(profile_a)
  profile_b["theme_name"] = "updated theme"
  assert _stable_payload_signature(profile_a) != _stable_payload_signature(profile_b)


def test_build_search_plan_view_contains_global_web_plan() -> None:
  view = _build_search_plan_view(_profile(), _default_search_plan_settings(_profile()), [])
  assert "global_web_plan" in view["plan"]
  assert view["summary"]["discovery_query_count"] > 0


def test_manual_query_is_preserved_in_search_plan_view() -> None:
  manual_query = _normalize_manual_query(
    {
      "source": "patent",
      "language": "ja",
      "strategy": "manual_focus",
      "query_text": "\"PAN系炭素繊維前駆体\" AND \"表面欠陥\"",
    }
  )
  view = _build_search_plan_view(_profile(), _default_search_plan_settings(_profile()), [manual_query])
  assert len(view["manual_queries"]) == 1
  assert view["manual_queries"][0]["origin"] == "manual"


def test_manual_query_survives_theme_change_when_passed_back_in() -> None:
  manual_query = _normalize_manual_query(
    {
      "source": "global_web",
      "country_region_code": "JP",
      "web_intent": "research_development",
      "result_bucket": "web",
      "priority": "high",
      "query_local": "PAN系炭素繊維前駆体 研究開発",
      "max_results": 10,
    }
  )
  profile_b = deepcopy(_profile())
  profile_b["theme_description"] = "updated description"
  view = _build_search_plan_view(profile_b, _default_search_plan_settings(profile_b), [manual_query])
  assert view["manual_queries"][0]["query_local"] == "PAN系炭素繊維前駆体 研究開発"


def test_ui_code_contains_theme_regenerate_button() -> None:
  assert "検索計画を再生成" in TABS_SOURCE


def test_ui_code_contains_integrated_search_plan_summary_labels() -> None:
  required_labels = [
    "統合検索計画サマリー",
    "国・地域coverage",
    "Discovery query数",
    "Verification予定件数",
    "翻訳予定件数",
    "Provider routing",
    "validation結果",
  ]
  assert all(label in TABS_SOURCE for label in required_labels)


def test_ui_code_contains_plan_expander_labels() -> None:
  required_labels = ["特許計画", "論文計画", "Web計画", "企業計画", "Global Web計画"]
  assert all(label in TABS_SOURCE for label in required_labels)


def test_ui_code_contains_manual_query_labels() -> None:
  required_labels = ["手動query", "手動queryを追加", "削除", "origin=", "manual", "generated"]
  assert all(label in TABS_SOURCE for label in required_labels)


def test_ui_code_contains_search_plan_state_management() -> None:
  required_tokens = [
    "STATE_SEARCH_PLAN_DATA",
    "STATE_SEARCH_PLAN_STATUS_MESSAGE",
    "STATE_SEARCH_PLAN_FORCE_REGENERATE",
    "_refresh_search_plan_state(",
  ]
  assert all(token in APP_SOURCE for token in required_tokens)


def test_query_delete_button_key_includes_query_id() -> None:
  assert 'f"delete_manual_query_{query_id}"' in TABS_SOURCE


def test_ui_code_does_not_call_external_apis() -> None:
  combined_source = TABS_SOURCE + "\n" + APP_SOURCE
  banned_tokens = [
    "import requests",
    "import httpx",
    "from openai",
    "google.generativeai",
    "WebSearch(",
    "CallMcpTool(",
  ]
  assert all(token not in combined_source for token in banned_tokens)


def test_streamlit_testing_finds_search_plan_controls_and_summary() -> None:
  at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
  at.run()
  texts = []
  for collection_name in ["markdown", "caption", "info", "warning", "text"]:
    for item in getattr(at, collection_name, []):
      value = getattr(item, "value", None) or getattr(item, "body", None) or getattr(item, "label", None)
      if value:
        texts.append(str(value))
  assert any("検索計画状態" in text for text in texts)
  assert any("統合検索計画サマリー" in text for text in texts)
  assert any("国・地域coverage" in text for text in texts)
  assert any("Provider routing" in text for text in texts)


def test_streamlit_testing_finds_regenerate_and_manual_query_widgets() -> None:
  at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
  at.run()
  assert any(button.label == "検索計画を再生成" for button in at.button)
  assert any(button.label == "情報源設定で検索計画を再生成" for button in at.button)
  assert any(button.label in {"手動queryを追加", "Global Web手動queryを追加"} for button in at.button)
  assert any(select.label == "手動queryの対象" for select in at.selectbox)


def test_streamlit_testing_keeps_upload_widgets() -> None:
  at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
  at.run()
  assert any(uploader.label == "CSVファイル" for uploader in at.file_uploader)
  assert any(uploader.label == "JSONファイル" for uploader in at.file_uploader)
  assert any(radio.label == "データ投入モード" for radio in at.radio)
