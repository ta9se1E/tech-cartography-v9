"""Tests for v9 score explanation UI display helpers and wiring."""

from __future__ import annotations

from pathlib import Path

from services_v9.demo_data import load_demo_signals_payload, load_demo_watch_profile_payload
from services_v9.score_explainer import attach_score_explanations
from ui_v9.labels import score_level_label_ja
from ui_v9.tabs import _merge_keyword_hits

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABS_SOURCE = (PROJECT_ROOT / "ui_v9" / "tabs.py").read_text(encoding="utf-8")
APP_SOURCE = (PROJECT_ROOT / "ui_v9" / "signal_watch_app.py").read_text(encoding="utf-8")


def _sample_explanation() -> dict:
  return {
    "matched_keywords": {
      "core_en": ["PAN", "PAN"],
      "core_ja": ["前駆体"],
      "application_en": ["carbon fiber"],
      "application_ja": ["炭素繊維"],
      "material_process_en": ["spinning"],
      "material_process_ja": ["凝固浴"],
      "target_companies": ["Demo Corp"],
    },
    "exclude_hits": {
      "exclude_en": ["graphene"],
      "exclude_ja": ["汎用ニュース"],
    },
  }


def _uploaded_signal() -> dict:
  return {
    "id": "upload_001",
    "title": "PAN precursor upload",
    "type": "patent",
    "summary": "前駆体と炭素繊維の凝固浴条件を扱う。",
    "tags": ["PAN", "carbon fiber", "spinning"],
    "why_read": "Demo Corp の確認に使える。",
    "what_to_check": "内部ボイドを確認する。",
    "next_action": "凝固浴条件を整理する。",
    "companies": ["Demo Corp"],
    "source_name": "Upload Source",
    "score": 0.82,
    "action": "Read Now",
  }


def _uploaded_profile() -> dict:
  return {
    "schema_version": "v9.2",
    "keywords": {
      "core_en": ["PAN"],
      "core_ja": ["前駆体"],
      "application_en": ["carbon fiber"],
      "application_ja": ["炭素繊維"],
      "material_process_en": ["spinning"],
      "material_process_ja": ["凝固浴"],
      "exclude_en": ["graphene"],
      "exclude_ja": ["汎用ニュース"],
    },
    "target_companies": ["Demo Corp"],
  }


def test_score_level_high_is_translated() -> None:
  assert score_level_label_ja("high") == "高"


def test_score_level_medium_is_translated() -> None:
  assert score_level_label_ja("medium") == "中"


def test_score_level_low_is_translated() -> None:
  assert score_level_label_ja("low") == "低"


def test_unknown_score_level_does_not_fail() -> None:
  assert score_level_label_ja("other") == "other"


def test_merge_core_en_and_core_ja_hits() -> None:
  values = _merge_keyword_hits(_sample_explanation()["matched_keywords"], ["core_en", "core_ja"])
  assert values == ["PAN", "前駆体"]


def test_merge_application_en_and_application_ja_hits() -> None:
  values = _merge_keyword_hits(_sample_explanation()["matched_keywords"], ["application_en", "application_ja"])
  assert values == ["carbon fiber", "炭素繊維"]


def test_merge_material_process_en_and_material_process_ja_hits() -> None:
  values = _merge_keyword_hits(_sample_explanation()["matched_keywords"], ["material_process_en", "material_process_ja"])
  assert values == ["spinning", "凝固浴"]


def test_merge_exclude_en_and_exclude_ja_hits() -> None:
  values = _merge_keyword_hits(_sample_explanation()["exclude_hits"], ["exclude_en", "exclude_ja"])
  assert values == ["graphene", "汎用ニュース"]


def test_merge_keyword_hits_deduplicates_values() -> None:
  values = _merge_keyword_hits({"core_en": ["PAN", "PAN", "pan"]}, ["core_en"])
  assert values == ["PAN"]


def test_merge_keyword_hits_preserves_order() -> None:
  values = _merge_keyword_hits({"core_en": ["B", "A"], "core_ja": ["C"]}, ["core_en", "core_ja"])
  assert values == ["B", "A", "C"]


def test_merge_keyword_hits_returns_empty_list_when_keys_missing() -> None:
  assert _merge_keyword_hits({}, ["core_en", "core_ja"]) == []


def test_merge_keyword_hits_returns_empty_list_for_none() -> None:
  assert _merge_keyword_hits(None, ["core_en", "core_ja"]) == []


def test_can_generate_signal_with_score_explanation() -> None:
  explained = attach_score_explanations([_uploaded_signal()], _uploaded_profile())
  assert "score_explanation" in explained[0]


def test_can_attach_score_explanation_to_demo_signal() -> None:
  demo_signal = load_demo_signals_payload()[0]
  explained = attach_score_explanations([demo_signal], load_demo_watch_profile_payload())
  assert "score_explanation" in explained[0]


def test_can_attach_score_explanation_to_uploaded_signal() -> None:
  explained = attach_score_explanations([_uploaded_signal()], _uploaded_profile())
  assert explained[0]["score_explanation"]["matched_keywords"]["core_en"] == ["PAN"]


def test_attach_score_explanations_does_not_mutate_original_signal() -> None:
  signal = _uploaded_signal()
  original = dict(signal)
  explained = attach_score_explanations([signal], _uploaded_profile())
  assert signal == original
  assert "score_explanation" not in signal
  assert "score_explanation" in explained[0]


def test_ui_code_contains_score_explanation_expander_label() -> None:
  assert "スコア根拠を確認" in TABS_SOURCE


def test_ui_code_contains_core_keyword_label() -> None:
  assert "一致したコアキーワード" in TABS_SOURCE


def test_ui_code_contains_material_process_keyword_label() -> None:
  assert "一致した材料・プロセスキーワード" in TABS_SOURCE


def test_ui_code_contains_exclude_keyword_label() -> None:
  assert "除外キーワード一致" in TABS_SOURCE


def test_ui_code_does_not_yet_include_review_input_labels() -> None:
  banned_labels = ["レビューコメント", "レビュー優先度", "採用 / 保留 / 見送り", "review_comment"]
  assert all(label not in TABS_SOURCE for label in banned_labels)


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
