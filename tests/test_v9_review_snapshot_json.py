"""Tests for v9 review-aware snapshot and JSON export."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from services_v9.demo_data import (
  SAMPLE_UPLOAD_CSV_PATH,
  SAMPLE_UPLOAD_JSON_PATH,
  load_demo_signals_payload,
  load_demo_watch_profile_payload,
)
from services_v9.digest_export import signals_to_csv, signals_to_json
from services_v9.persistence import load_snapshot, save_digest_files, save_snapshot
from services_v9.signal_loader import load_signals_from_csv_text, load_signals_from_json_text, prepare_uploaded_signals
from services_v9.signal_models import Signal, WatchProfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (PROJECT_ROOT / "ui_v9" / "signal_watch_app.py").read_text(encoding="utf-8")
TABS_SOURCE = (PROJECT_ROOT / "ui_v9" / "tabs.py").read_text(encoding="utf-8")
DIGEST_SOURCE = (PROJECT_ROOT / "services_v9" / "digest_export.py").read_text(encoding="utf-8")


def _watch_profile() -> WatchProfile:
  return WatchProfile.from_dict(load_demo_watch_profile_payload())


def _signal(
  signal_id: str,
  *,
  title: str = "PAN系前駆体の内部ボイド低減に関する情報",
  reviewed: bool = True,
  decision: str = "採用",
  priority: int = 1,
  comment: str = "Seed公報との関係を確認する",
) -> dict[str, object]:
  return {
    "id": signal_id,
    "title": title,
    "type": "patent",
    "source_url": f"https://example.com/{signal_id}",
    "source_name": "Demo",
    "published_date": "2026-07-04",
    "summary": "summary",
    "score": 0.82,
    "previous_score": None,
    "status": "New",
    "action": "Read Now",
    "why_read": "w",
    "what_to_check": "c",
    "next_action": "n",
    "tags": [],
    "companies": [],
    "review": {
      "review_decision": decision,
      "review_priority": priority,
      "review_comment": comment,
      "reviewed": reviewed,
    },
  }


def test_reviewed_true_review_is_retained_in_signal() -> None:
  signal = _signal("a", reviewed=True)
  assert signal["review"]["reviewed"] is True


def test_reviewed_false_review_is_retained_in_signal() -> None:
  signal = _signal("a", reviewed=False, decision="保留", priority=2, comment="次回更新まで監視")
  assert signal["review"]["reviewed"] is False


def test_review_decision_is_retained() -> None:
  signal = _signal("a", decision="見送り", priority=3, comment="対象外")
  assert signal["review"]["review_decision"] == "見送り"


def test_review_priority_is_retained_as_integer() -> None:
  signal = _signal("a", priority=2)
  assert isinstance(signal["review"]["review_priority"], int)
  assert signal["review"]["review_priority"] == 2


def test_review_comment_can_store_japanese_text() -> None:
  signal = _signal("a", comment="日本語コメント")
  assert signal["review"]["review_comment"] == "日本語コメント"


def test_can_save_snapshot_with_reviewed_signal(tmp_path: Path) -> None:
  path = save_snapshot([_signal("a")], _watch_profile().to_dict(), run_note="review", base_dir=tmp_path / "v9_runs")
  assert path.exists()


def test_can_load_saved_snapshot(tmp_path: Path) -> None:
  path = save_snapshot([_signal("a")], _watch_profile().to_dict(), run_note="review", base_dir=tmp_path / "v9_runs")
  payload = load_snapshot(path)
  assert payload["run_note"] == "review"


def test_loaded_snapshot_contains_review(tmp_path: Path) -> None:
  path = save_snapshot([_signal("a")], _watch_profile().to_dict(), run_note="review", base_dir=tmp_path / "v9_runs")
  payload = load_snapshot(path)
  assert payload["signals"][0]["review"]["reviewed"] is True


def test_legacy_signal_without_review_can_be_saved_to_snapshot(tmp_path: Path) -> None:
  signal = {key: value for key, value in _signal("a").items() if key != "review"}
  path = save_snapshot([signal], _watch_profile().to_dict(), run_note="legacy", base_dir=tmp_path / "v9_runs")
  assert path.exists()


def test_legacy_snapshot_without_review_can_be_loaded(tmp_path: Path) -> None:
  signal = {key: value for key, value in _signal("a").items() if key != "review"}
  path = save_snapshot([signal], _watch_profile().to_dict(), run_note="legacy", base_dir=tmp_path / "v9_runs")
  payload = load_snapshot(path)
  assert "review" not in payload["signals"][0]


def test_json_export_includes_review() -> None:
  payload = json.loads(signals_to_json([_signal("a")], _watch_profile()))
  assert "review" in payload["signals"][0]


def test_json_export_keeps_reviewed_true_as_bool() -> None:
  payload = json.loads(signals_to_json([_signal("a", reviewed=True)], _watch_profile()))
  assert payload["signals"][0]["review"]["reviewed"] is True


def test_json_export_keeps_reviewed_false_as_bool() -> None:
  payload = json.loads(signals_to_json([_signal("a", reviewed=False, decision="保留", priority=2, comment="次回更新まで監視")], _watch_profile()))
  assert payload["signals"][0]["review"]["reviewed"] is False


def test_json_export_keeps_japanese_comment_without_mojibake() -> None:
  payload_text = signals_to_json([_signal("a", comment="日本語コメント")], _watch_profile())
  assert "日本語コメント" in payload_text


def test_json_export_keeps_watch_profile() -> None:
  payload = json.loads(signals_to_json([_signal("a")], _watch_profile()))
  assert payload["watch_profile"]["schema_version"] == "v9.2"


def test_json_export_keeps_data_source() -> None:
  payload = json.loads(signals_to_json([_signal("a")], _watch_profile(), data_source="JSONアップロード"))
  assert payload["data_source"] == "JSONアップロード"


def test_digest_saved_json_includes_review(tmp_path: Path) -> None:
  json_text = signals_to_json([_signal("a")], _watch_profile())
  saved = save_digest_files("# digest", signals_to_csv([]), json_text, snapshot_id="2026-07-04_001", base_dir=tmp_path / "v9_runs")
  payload = json.loads(saved["json"].read_text(encoding="utf-8"))
  assert payload["signals"][0]["review"]["reviewed"] is True


def test_csv_header_is_unchanged() -> None:
  signal = Signal.from_dict(_signal("a"))
  header = signals_to_csv([signal]).splitlines()[0]
  assert header == "ID,タイトル,種別,出典名,出典URL,公開日,スコア,前回スコア,変化,判断,なぜ読むべきか,確認すべき点,次の行動,タグ,企業"


def test_csv_has_no_review_specific_columns() -> None:
  signal = Signal.from_dict(_signal("a"))
  header = signals_to_csv([signal]).splitlines()[0]
  assert "review" not in header
  assert "review_decision" not in header


def test_original_signal_is_not_mutated_by_snapshot_or_json(tmp_path: Path) -> None:
  signal = _signal("a")
  original = deepcopy(signal)
  signals_to_json([signal], _watch_profile())
  save_snapshot([signal], _watch_profile().to_dict(), run_note="review", base_dir=tmp_path / "v9_runs")
  assert signal == original


def test_empty_signal_list_can_generate_json() -> None:
  payload = json.loads(signals_to_json([], _watch_profile()))
  assert payload["signals"] == []


def test_demo_data_equivalent_works() -> None:
  signals = deepcopy(load_demo_signals_payload()[:2])
  signals[0]["review"] = _signal("demo-review")["review"]
  payload = json.loads(signals_to_json(signals, _watch_profile(), data_source="デモデータ", loaded_count=len(signals)))
  assert len(payload["signals"]) == 2


def test_csv_upload_data_equivalent_works() -> None:
  records, warnings = load_signals_from_csv_text(SAMPLE_UPLOAD_CSV_PATH.read_text(encoding="utf-8"))
  assert warnings == []
  prepared, prepared_warnings = prepare_uploaded_signals(records, load_demo_watch_profile_payload())
  assert prepared_warnings == []
  prepared[0]["review"] = _signal("csv-review")["review"]
  payload = json.loads(signals_to_json(prepared, _watch_profile(), data_source="CSVアップロード", loaded_count=len(prepared)))
  assert payload["data_source"] == "CSVアップロード"


def test_json_upload_data_equivalent_works() -> None:
  records, warnings = load_signals_from_json_text(SAMPLE_UPLOAD_JSON_PATH.read_text(encoding="utf-8"))
  assert warnings == []
  prepared, prepared_warnings = prepare_uploaded_signals(records, load_demo_watch_profile_payload())
  assert prepared_warnings == []
  prepared[0]["review"] = _signal("json-review")["review"]
  payload = json.loads(signals_to_json(prepared, _watch_profile(), data_source="JSONアップロード", loaded_count=len(prepared)))
  assert payload["data_source"] == "JSONアップロード"


def test_ui_code_passes_reviewed_signals_to_snapshot_save() -> None:
  assert "signals=latest_reviewed_signals" in APP_SOURCE


def test_ui_code_passes_reviewed_signals_to_json_export() -> None:
  assert "json_text = signals_to_json(\n    latest_reviewed_signals," in APP_SOURCE


def test_ui_code_does_not_add_review_restore_button() -> None:
  combined_source = APP_SOURCE + "\n" + TABS_SOURCE
  assert "review_restore" not in combined_source
  assert "レビュー復元" not in combined_source


def test_code_does_not_call_external_apis() -> None:
  combined_source = APP_SOURCE + "\n" + TABS_SOURCE + "\n" + DIGEST_SOURCE
  banned_tokens = [
    "import requests",
    "import httpx",
    "from openai",
    "google.generativeai",
    "WebSearch(",
    "CallMcpTool(",
  ]
  assert all(token not in combined_source for token in banned_tokens)
