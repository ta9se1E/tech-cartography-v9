"""Tests for v9 CSV/JSON signal upload and staged loader."""

from __future__ import annotations

import json

from services_v9.demo_data import load_demo_watch_profile_payload
from services_v9.digest_export import build_weekly_digest_markdown, signals_to_json
from services_v9.signal_loader import (
  load_signals_from_csv_text,
  load_signals_from_json_text,
  normalize_signal_record,
  prepare_uploaded_signals,
  score_signal_with_profile,
)
from services_v9.signal_models import Signal, WatchProfile
from services_v9.signal_template import build_csv_template, build_json_template


def _watch_profile() -> dict:
  return {
    "schema_version": "v9.2",
    "theme_name": "PAN前駆体欠陥監視",
    "theme_description": "前駆体の内部ボイドと表面欠陥を監視する",
    "keywords": {
      "core_en": ["PAN"],
      "core_ja": ["前駆体"],
      "application_en": ["carbon fiber"],
      "application_ja": ["炭素繊維"],
      "material_process_en": ["void"],
      "material_process_ja": ["内部ボイド"],
      "exclude_en": ["graphene"],
      "exclude_ja": ["汎用ニュース"],
    },
    "seed_publications": ["JP2022090764A"],
    "candidate_publications": [],
    "target_companies": ["Demo Corp", "東レ"],
    "countries": ["JP"],
    "source_types": ["patent", "paper", "company"],
    "cadence": "weekly",
    "priority_rules": [],
    "notes": "",
  }


def test_load_japanese_csv() -> None:
  csv_text = (
    "タイトル,種別,概要,タグ,企業\n"
    "日本語特許,特許,PAN前駆体の内部ボイドを扱う,前駆体,東レ\n"
  )
  records, warnings = load_signals_from_csv_text(csv_text)
  assert len(records) == 1
  assert warnings == []
  assert records[0]["title"] == "日本語特許"
  assert records[0]["type"] == "patent"


def test_load_english_csv() -> None:
  csv_text = "title,type,summary,tags,companies\nEnglish paper,article,About carbon fiber,PAN,Demo Corp\n"
  records, warnings = load_signals_from_csv_text(csv_text)
  assert len(records) == 1
  assert warnings == []
  assert records[0]["title"] == "English paper"
  assert records[0]["type"] == "paper"


def test_load_json_list_format() -> None:
  json_text = json.dumps([{"title": "List patent", "type": "patent"}], ensure_ascii=False)
  records, warnings = load_signals_from_json_text(json_text)
  assert len(records) == 1
  assert warnings == []
  assert records[0]["type"] == "patent"


def test_load_json_signals_wrapper_format() -> None:
  json_text = json.dumps({"signals": [{"title": "Wrapped company", "type": "company"}]}, ensure_ascii=False)
  records, warnings = load_signals_from_json_text(json_text)
  assert len(records) == 1
  assert warnings == []
  assert records[0]["type"] == "company"


def test_normalize_japanese_column_aliases() -> None:
  record, warnings = normalize_signal_record({"タイトル": "A", "種別": "特許", "変化": "新規", "判断": "今すぐ読む"})
  assert warnings == []
  assert record is not None
  assert record["title"] == "A"
  assert record["type"] == "patent"
  assert record["status"] == "New"
  assert record["action"] == "Read Now"


def test_normalize_english_column_aliases() -> None:
  record, warnings = normalize_signal_record({"title": "B", "type": "paper", "status": "Rising", "action": "Watch"})
  assert warnings == []
  assert record is not None
  assert record["title"] == "B"
  assert record["type"] == "paper"
  assert record["status"] == "Rising"
  assert record["action"] == "Watch"


def test_normalize_signal_types() -> None:
  patent, _ = normalize_signal_record({"title": "P", "type": "特許"})
  paper, _ = normalize_signal_record({"title": "A", "type": "論文"})
  web, _ = normalize_signal_record({"title": "W", "type": "Web情報"})
  company, _ = normalize_signal_record({"title": "C", "type": "企業情報"})
  assert patent and patent["type"] == "patent"
  assert paper and paper["type"] == "paper"
  assert web and web["type"] == "web"
  assert company and company["type"] == "company"


def test_title_and_type_only_can_become_signal() -> None:
  prepared, warnings = prepare_uploaded_signals([{"title": "Only required", "type": "patent"}], _watch_profile())
  assert len(prepared) == 1
  assert warnings == []
  assert prepared[0]["source_name"] == "アップロードデータ"
  assert prepared[0]["why_read"]
  assert prepared[0]["what_to_check"]
  assert prepared[0]["next_action"]


def test_missing_id_is_filled() -> None:
  records, _ = load_signals_from_csv_text("title,type\nFilled ID,patent\n")
  assert records[0]["id"] == "upload_001"


def test_profile_scoring_fills_missing_score() -> None:
  prepared, _ = prepare_uploaded_signals(
    [
      {
        "title": "PAN前駆体の内部ボイド低減",
        "type": "patent",
        "summary": "PAN前駆体と内部ボイドを扱う",
        "tags": "PAN,内部ボイド",
        "companies": "東レ",
      }
    ],
    _watch_profile(),
  )
  assert 0.0 <= prepared[0]["score"] <= 1.0
  assert prepared[0]["score"] > 0.45


def test_exclude_keyword_lowers_score() -> None:
  base_score = score_signal_with_profile(
    {
      "title": "PAN前駆体の内部ボイド低減",
      "summary": "内部ボイドを扱う",
      "tags": ["PAN", "内部ボイド"],
      "companies": ["東レ"],
      "type": "patent",
    },
    _watch_profile(),
  )
  penalized_score = score_signal_with_profile(
    {
      "title": "PAN前駆体の内部ボイド低減 graphene",
      "summary": "内部ボイドとgrapheneを扱う",
      "tags": ["PAN", "内部ボイド", "graphene"],
      "companies": ["東レ"],
      "type": "patent",
    },
    _watch_profile(),
  )
  assert penalized_score < base_score


def test_warnings_are_returned_in_japanese() -> None:
  prepared, warnings = prepare_uploaded_signals(
    [{"title": "Unknown type upload", "type": "mystery"}],
    _watch_profile(),
  )
  assert len(prepared) == 1
  assert warnings
  assert any("不明な種別" in warning for warning in warnings)


def test_csv_template_contains_japanese_columns() -> None:
  template = build_csv_template()
  assert "タイトル,種別,出典URL" in template
  assert "デモ特許" in template


def test_json_template_can_be_loaded() -> None:
  template = build_json_template()
  records, warnings = load_signals_from_json_text(template)
  assert len(records) == 3
  assert warnings == []


def test_uploaded_signals_can_flow_into_digest() -> None:
  records, _ = load_signals_from_json_text(build_json_template())
  prepared, _ = prepare_uploaded_signals(records, load_demo_watch_profile_payload())
  signals = [Signal.from_dict(item) for item in prepared]
  watch_profile = WatchProfile.from_dict(load_demo_watch_profile_payload())
  digest = build_weekly_digest_markdown(signals, watch_profile, data_source="JSONアップロード", loaded_count=len(signals))
  export_json = signals_to_json(signals, watch_profile, data_source="JSONアップロード", loaded_count=len(signals))
  assert "データソース: JSONアップロード" in digest
  assert f"読み込み件数: {len(signals)}件" in digest
  assert "\"data_source\": \"JSONアップロード\"" in export_json
