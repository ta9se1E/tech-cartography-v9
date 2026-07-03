"""Tests for the v9 score explanation core."""

from __future__ import annotations

from copy import deepcopy

from services_v9.score_explainer import (
  attach_score_explanations,
  build_signal_text_blob,
  explain_action,
  explain_signal_score,
  find_keyword_hits,
)


def _sample_profile() -> dict:
  return {
    "schema_version": "v9.2",
    "theme_name": "score explainer demo",
    "keywords": {
      "core_en": ["PAN", "precursor"],
      "core_ja": ["前駆体", "内部ボイド"],
      "application_en": ["carbon fiber"],
      "application_ja": ["炭素繊維"],
      "material_process_en": ["spinning", "void"],
      "material_process_ja": ["凝固浴", "毛羽"],
      "exclude_en": ["graphene"],
      "exclude_ja": ["汎用ニュース"],
    },
    "target_companies": ["Demo Corp", "東レ"],
  }


def _sample_signal(**overrides) -> dict:
  signal = {
    "title": "PAN precursor spinning update",
    "summary": "前駆体と炭素繊維の内部ボイド、凝固浴条件を扱う。",
    "tags": ["PAN", "carbon fiber", "spinning"],
    "why_read": "Demo Corp と東レの工程比較に使える。",
    "what_to_check": "graphene ではなく凝固浴条件を確認する。",
    "next_action": "毛羽とvoidの関係を整理する。",
    "companies": ["Demo Corp", "東レ"],
    "source_name": "Demo Source",
    "score": 0.82,
    "action": "Read Now",
  }
  signal.update(overrides)
  return signal


def test_build_signal_text_blob_joins_signal_fields() -> None:
  blob = build_signal_text_blob(_sample_signal())
  assert "PAN precursor spinning update" in blob
  assert "Demo Source" in blob


def test_build_signal_text_blob_handles_list_tags() -> None:
  blob = build_signal_text_blob(_sample_signal(tags=["tag-a", "tag-b"]))
  assert "tag-a" in blob
  assert "tag-b" in blob


def test_build_signal_text_blob_handles_list_companies() -> None:
  blob = build_signal_text_blob(_sample_signal(companies=["Demo Corp", "東レ"]))
  assert "Demo Corp" in blob
  assert "東レ" in blob


def test_find_keyword_hits_matches_english_case_insensitively() -> None:
  hits = find_keyword_hits("PAN precursor update", ["pan", "PRECURSOR"])
  assert hits == ["pan", "PRECURSOR"]


def test_find_keyword_hits_matches_japanese_keywords() -> None:
  hits = find_keyword_hits("前駆体の内部ボイド評価", ["前駆体", "内部ボイド"])
  assert hits == ["前駆体", "内部ボイド"]


def test_find_keyword_hits_ignores_empty_keywords() -> None:
  hits = find_keyword_hits("PAN precursor update", ["", " ", "PAN"])
  assert hits == ["PAN"]


def test_find_keyword_hits_deduplicates_hits() -> None:
  hits = find_keyword_hits("PAN precursor update", ["PAN", "pan", "PAN"])
  assert hits == ["PAN"]


def test_explain_signal_score_returns_core_en_hits() -> None:
  explanation = explain_signal_score(_sample_signal(), _sample_profile())
  assert explanation["matched_keywords"]["core_en"] == ["PAN", "precursor"]


def test_explain_signal_score_returns_core_ja_hits() -> None:
  explanation = explain_signal_score(_sample_signal(), _sample_profile())
  assert explanation["matched_keywords"]["core_ja"] == ["前駆体", "内部ボイド"]


def test_explain_signal_score_returns_application_en_hits() -> None:
  explanation = explain_signal_score(_sample_signal(), _sample_profile())
  assert explanation["matched_keywords"]["application_en"] == ["carbon fiber"]


def test_explain_signal_score_returns_application_ja_hits() -> None:
  explanation = explain_signal_score(_sample_signal(), _sample_profile())
  assert explanation["matched_keywords"]["application_ja"] == ["炭素繊維"]


def test_explain_signal_score_returns_material_process_en_hits() -> None:
  explanation = explain_signal_score(_sample_signal(), _sample_profile())
  assert explanation["matched_keywords"]["material_process_en"] == ["spinning", "void"]


def test_explain_signal_score_returns_material_process_ja_hits() -> None:
  explanation = explain_signal_score(_sample_signal(), _sample_profile())
  assert explanation["matched_keywords"]["material_process_ja"] == ["凝固浴", "毛羽"]


def test_explain_signal_score_returns_target_company_hits() -> None:
  explanation = explain_signal_score(_sample_signal(), _sample_profile())
  assert explanation["matched_keywords"]["target_companies"] == ["Demo Corp", "東レ"]


def test_explain_signal_score_returns_exclude_en_hits() -> None:
  explanation = explain_signal_score(_sample_signal(), _sample_profile())
  assert explanation["exclude_hits"]["exclude_en"] == ["graphene"]


def test_explain_signal_score_returns_exclude_ja_hits() -> None:
  signal = _sample_signal(summary="前駆体の汎用ニュースです。")
  explanation = explain_signal_score(signal, _sample_profile())
  assert explanation["exclude_hits"]["exclude_ja"] == ["汎用ニュース"]


def test_score_level_high_for_075_or_more() -> None:
  explanation = explain_signal_score(_sample_signal(score=0.75), _sample_profile())
  assert explanation["score_level"] == "high"


def test_score_level_medium_for_055_or_more() -> None:
  explanation = explain_signal_score(_sample_signal(score=0.55), _sample_profile())
  assert explanation["score_level"] == "medium"


def test_score_level_low_below_055() -> None:
  explanation = explain_signal_score(_sample_signal(score=0.54), _sample_profile())
  assert explanation["score_level"] == "low"


def test_explain_action_returns_read_now_reason_in_japanese() -> None:
  assert "今週優先して読む候補" in explain_action({"action": "Read Now"})


def test_explain_action_returns_watch_reason_in_japanese() -> None:
  assert "継続監視候補" in explain_action({"action": "Watch"})


def test_explain_action_returns_ignore_reason_in_japanese() -> None:
  assert "見送り候補" in explain_action({"action": "Ignore"})


def test_explain_signal_score_handles_missing_profile_keys() -> None:
  explanation = explain_signal_score(_sample_signal(), {"schema_version": "v9.2"})
  assert explanation["matched_keywords"]["core_en"] == []
  assert explanation["exclude_hits"]["exclude_en"] == []


def test_attach_score_explanations_adds_explanations() -> None:
  explained = attach_score_explanations([_sample_signal()], _sample_profile())
  assert "score_explanation" in explained[0]
  assert explained[0]["score_explanation"]["score_level"] == "high"


def test_attach_score_explanations_does_not_mutate_original_signal() -> None:
  signal = _sample_signal()
  original = deepcopy(signal)
  explained = attach_score_explanations([signal], _sample_profile())
  assert signal == original
  assert "score_explanation" not in signal
  assert "score_explanation" in explained[0]
