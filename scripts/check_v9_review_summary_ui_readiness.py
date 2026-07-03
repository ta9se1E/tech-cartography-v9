"""Readiness checks for the v9 review summary UI."""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.review_state import apply_reviews_to_signals, summarize_reviews  # noqa: E402
from ui_v9.signal_watch_app import _stable_signal_id  # noqa: E402
from ui_v9.tabs import _review_progress, _select_adopted_signals, _select_unreviewed_signals  # noqa: E402


def main() -> int:
  errors: list[str] = []

  base_signal = {
    "title": "PAN precursor demo",
    "type": "patent",
    "source_url": "https://example.com/demo",
    "source_name": "Demo Source",
    "published_date": "2026-07-04",
    "summary": "前駆体の比較",
    "tags": ["PAN"],
    "companies": ["Demo Corp"],
    "action": "Read Now",
    "score": 0.82,
  }
  current_signals = [
    {**base_signal, "id": "signal_001"},
    {**base_signal, "id": "signal_002", "title": "Paper signal", "type": "paper", "action": "Watch", "score": 0.68},
    {**base_signal, "title": "Generated signal", "source_url": "https://example.com/generated", "action": "Ignore", "score": 0.40},
  ]
  original_signals = deepcopy(current_signals)

  with_ids = []
  for index, signal in enumerate(current_signals):
    copied = dict(signal)
    copied["id"] = _stable_signal_id(copied, index=index)
    with_ids.append(copied)

  reviews_by_signal_id = {
    with_ids[0]["id"]: {
      "review_decision": "採用",
      "review_priority": 1,
      "review_comment": "今週確認する",
      "reviewed": True,
    },
    with_ids[1]["id"]: {
      "review_decision": "保留",
      "review_priority": 2,
      "review_comment": "継続監視",
      "reviewed": True,
    },
  }

  reviewed_signals = apply_reviews_to_signals(with_ids, reviews_by_signal_id)
  summary = summarize_reviews(reviewed_signals)
  progress = _review_progress(summary)
  adopted = _select_adopted_signals(reviewed_signals, limit=10)
  unreviewed = _select_unreviewed_signals(reviewed_signals, limit=10)

  if len(reviewed_signals) != 3:
    errors.append("現在Signalへreviewを適用できません")
  if summary["採用"] < 1:
    errors.append("採用件数を取得できません")
  if summary["保留"] < 1:
    errors.append("保留件数を取得できません")
  if summary["見送り"] < 1:
    errors.append("見送り件数を取得できません")
  if summary["未レビュー"] < 1:
    errors.append("未レビュー件数を取得できません")
  if progress["total_count"] != 3 or progress["reviewed_count"] != 2:
    errors.append("review progressを計算できません")
  if _review_progress({"合計": 0, "未レビュー": 0})["ratio"] != 0.0:
    errors.append("total=0でもprogress計算が安定しません")
  if not adopted or str(adopted[0].get("review", {}).get("review_decision", "")) != "採用":
    errors.append("採用Signalを抽出できません")
  if not unreviewed or bool(unreviewed[0].get("review", {}).get("reviewed", True)):
    errors.append("未レビューSignalを抽出できません")

  other_source_signals = [
    {**base_signal, "id": "csv_signal_001", "title": "CSV signal", "source_url": "https://example.com/csv", "score": 0.55},
  ]
  other_reviewed = apply_reviews_to_signals(other_source_signals, reviews_by_signal_id)
  other_summary = summarize_reviews(other_reviewed)
  if other_summary["未レビュー"] != 1:
    errors.append("異なるデータソースのSignalを混在させています")

  if current_signals != original_signals:
    errors.append("元Signalを変更しています")

  if errors:
    print("[v9 review summary ui readiness] NG:")
    for error in errors:
      print(f"- {error}")
    return 1

  print("[v9 review summary ui readiness] OK: review summary UI is ready.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
