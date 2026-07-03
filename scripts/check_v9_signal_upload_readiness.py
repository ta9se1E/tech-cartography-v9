"""Readiness checks for v9 CSV/JSON signal upload."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.demo_data import SAMPLE_UPLOAD_CSV_PATH, SAMPLE_UPLOAD_JSON_PATH, load_demo_watch_profile_payload  # noqa: E402
from services_v9.digest_export import build_weekly_digest_markdown, signals_to_json  # noqa: E402
from services_v9.signal_loader import (  # noqa: E402
  load_signals_from_csv_text,
  load_signals_from_json_text,
  normalize_signal_record,
  prepare_uploaded_signals,
  score_signal_with_profile,
)
from services_v9.signal_models import Signal, WatchProfile  # noqa: E402
from services_v9.signal_template import build_csv_template, build_json_template  # noqa: E402
from services_v9.signal_upload_schema import normalize_signal_action, normalize_signal_status, normalize_signal_type  # noqa: E402


def main() -> int:
  errors: list[str] = []
  watch_profile = load_demo_watch_profile_payload()

  csv_template = build_csv_template()
  json_template = build_json_template()
  if "タイトル,種別" not in csv_template:
    errors.append("CSVテンプレートに日本語カラムが含まれていません")
  if "\"signals\"" not in json_template:
    errors.append("JSONテンプレートを生成できません")

  if not SAMPLE_UPLOAD_CSV_PATH.exists():
    errors.append("demo sample CSV が存在しません")
  if not SAMPLE_UPLOAD_JSON_PATH.exists():
    errors.append("demo sample JSON が存在しません")

  csv_records, csv_warnings = load_signals_from_csv_text(SAMPLE_UPLOAD_CSV_PATH.read_text(encoding="utf-8"))
  json_records, json_warnings = load_signals_from_json_text(SAMPLE_UPLOAD_JSON_PATH.read_text(encoding="utf-8"))
  if len(csv_records) < 3:
    errors.append("demo sample CSV を3件以上読み込めません")
  if len(json_records) < 3:
    errors.append("demo sample JSON を3件以上読み込めません")

  ja_record, ja_record_warnings = normalize_signal_record(
    {
      "タイトル": "日本語特許",
      "種別": "特許",
      "変化": "新規",
      "判断": "今すぐ読む",
    },
    row_index=1,
  )
  en_record, en_record_warnings = normalize_signal_record(
    {
      "title": "English paper",
      "type": "article",
      "status": "Rising",
      "action": "Watch",
    },
    row_index=2,
  )
  if not ja_record or ja_record["type"] != "patent":
    errors.append("日本語カラムの正規化に失敗しました")
  if not en_record or en_record["type"] != "paper":
    errors.append("英語カラムの正規化に失敗しました")
  if ja_record and ja_record["status"] != "New":
    errors.append("status正規化に失敗しました")
  if ja_record and ja_record["action"] != "Read Now":
    errors.append("action正規化に失敗しました")
  if ja_record_warnings or en_record_warnings:
    errors.append("正常な入力で不要なwarningが発生しました")

  type_value, type_warnings = normalize_signal_type("unknown-source")
  if type_value != "web" or not type_warnings:
    errors.append("typeのwarning付きfallbackに失敗しました")
  if normalize_signal_status("新規") != "New":
    errors.append("日本語statusの正規化に失敗しました")
  if normalize_signal_action("今すぐ読む") != "Read Now":
    errors.append("日本語actionの正規化に失敗しました")

  scored = score_signal_with_profile(
    {
      "title": "PAN 前駆体 内部ボイドの改善",
      "summary": "炭素繊維前駆体と内部ボイドを扱うメモ",
      "tags": ["PAN", "内部ボイド"],
      "companies": ["東レ"],
      "type": "patent",
    },
    watch_profile,
  )
  if not (0.0 <= scored <= 1.0):
    errors.append("Watch Profileに基づく仮スコアリングに失敗しました")

  prepared, prepared_warnings = prepare_uploaded_signals(
    [
      {"title": "Noisy upload", "type": "mystery"},
      {"title": "Valid upload", "type": "patent"},
    ],
    watch_profile,
  )
  if len(prepared) < 2:
    errors.append("uploaded signals の準備に失敗しました")
  if not any("不明な種別" in warning for warning in prepared_warnings):
    errors.append("読み込みwarningを返せません")

  digest = build_weekly_digest_markdown(
    [Signal.from_dict(item) for item in prepared],
    WatchProfile.from_dict(watch_profile),
    data_source="CSVアップロード",
    loaded_count=len(prepared),
  )
  json_text = signals_to_json(
    [Signal.from_dict(item) for item in prepared],
    WatchProfile.from_dict(watch_profile),
    data_source="CSVアップロード",
    loaded_count=len(prepared),
  )
  if "データソース: CSVアップロード" not in digest:
    errors.append("digestにデータソースを反映できません")
  if "\"data_source\": \"CSVアップロード\"" not in json_text:
    errors.append("export JSON に data_source を反映できません")

  if errors:
    print("[v9 signal upload readiness] NG:")
    for error in errors:
      print(f"- {error}")
    return 1

  print("[v9 signal upload readiness] OK: CSV/JSON signal upload loader is ready.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
