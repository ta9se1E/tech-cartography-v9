"""Readiness checks for the v9 review-aware snapshot and JSON export."""

from __future__ import annotations

import json
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.demo_data import load_demo_watch_profile_payload  # noqa: E402
from services_v9.digest_export import signals_to_csv, signals_to_json  # noqa: E402
from services_v9.persistence import load_snapshot, save_digest_files, save_snapshot  # noqa: E402
from services_v9.signal_models import WatchProfile  # noqa: E402


def _reviewed_signal(reviewed: bool) -> dict[str, object]:
  return {
    "id": "signal_001" if reviewed else "signal_002",
    "title": "PAN系前駆体の内部ボイド低減に関する情報",
    "type": "patent",
    "source_url": "https://example.com/signal",
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
      "review_decision": "採用" if reviewed else "保留",
      "review_priority": 1 if reviewed else 2,
      "review_comment": "Seed公報との関係を確認する" if reviewed else "次回更新まで監視",
      "reviewed": reviewed,
    },
  }


def main() -> int:
  errors: list[str] = []
  watch_profile = WatchProfile.from_dict(load_demo_watch_profile_payload())
  reviewed_true = _reviewed_signal(True)
  reviewed_false = _reviewed_signal(False)

  with tempfile.TemporaryDirectory() as tmp_dir_name:
    base_dir = Path(tmp_dir_name) / "v9_runs"

    before_snapshot = deepcopy([reviewed_true, reviewed_false])
    snapshot_path = save_snapshot([reviewed_true, reviewed_false], watch_profile.to_dict(), run_note="review", base_dir=base_dir)
    snapshot_payload = load_snapshot(snapshot_path)
    if snapshot_payload["signals"][0]["review"]["reviewed"] is not True:
      errors.append("reviewed=TrueのSignalをsnapshot保存できません")
    if snapshot_payload["signals"][1]["review"]["reviewed"] is not False:
      errors.append("reviewed=FalseのSignalをsnapshot保存できません")
    if snapshot_payload["signals"][0]["review"]["review_comment"] != "Seed公報との関係を確認する":
      errors.append("review_commentを日本語で保存できません")
    if snapshot_payload["signals"][0]["review"]["review_priority"] != 1:
      errors.append("review_priorityを整数で保存できません")
    if [reviewed_true, reviewed_false] != before_snapshot:
      errors.append("save_snapshotが元Signalを変更しています")

    legacy_snapshot_path = save_snapshot(
      [{key: value for key, value in reviewed_true.items() if key != "review"}],
      watch_profile.to_dict(),
      run_note="legacy",
      base_dir=base_dir,
    )
    legacy_payload = load_snapshot(legacy_snapshot_path)
    if "review" in legacy_payload["signals"][0]:
      errors.append("reviewなし旧snapshotの互換性が壊れています")

    json_text = signals_to_json([reviewed_true, reviewed_false], watch_profile, data_source="CSVアップロード", loaded_count=2)
    json_payload = json.loads(json_text)
    review_payload = json_payload["signals"][0]["review"]
    if review_payload["reviewed"] is not True or json_payload["signals"][1]["review"]["reviewed"] is not False:
      errors.append("JSON Exportにreviewed=True/Falseを保持できません")
    if review_payload["review_comment"] != "Seed公報との関係を確認する":
      errors.append("JSON Exportに日本語レビューコメントを保持できません")
    if json_payload["data_source"] != "CSVアップロード":
      errors.append("JSON Exportでdata_sourceを保持できません")

    digest_saved = save_digest_files(
      markdown="# digest",
      csv_text=signals_to_csv([]),
      json_text=json_text,
      snapshot_id="2026-07-04_001",
      base_dir=base_dir,
    )
    saved_json_payload = json.loads(digest_saved["json"].read_text(encoding="utf-8"))
    if "review" not in saved_json_payload["signals"][0]:
      errors.append("Digest保存用JSONにreviewが含まれていません")

    csv_header = signals_to_csv([]).splitlines()[0]
    if "review" in csv_header or "review_decision" in csv_header:
      errors.append("CSV Exportのヘッダーが変更されています")

  combined_source = (
    (PROJECT_ROOT / "ui_v9" / "signal_watch_app.py").read_text(encoding="utf-8")
    + "\n"
    + (PROJECT_ROOT / "services_v9" / "digest_export.py").read_text(encoding="utf-8")
  )
  banned_tokens = [
    "import requests",
    "import httpx",
    "from openai",
    "google.generativeai",
    "WebSearch(",
    "CallMcpTool(",
  ]
  if any(token in combined_source for token in banned_tokens):
    errors.append("外部APIなしで完結していません")

  if errors:
    print("[v9 review snapshot json readiness] NG:")
    for error in errors:
      print(f"- {error}")
    return 1

  print("[v9 review snapshot json readiness] OK: review-aware snapshot and JSON export are ready.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
