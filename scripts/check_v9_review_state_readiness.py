"""Readiness checks for the v9 human review state core."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.review_state import (  # noqa: E402
  apply_review_to_signal,
  apply_reviews_to_signals,
  default_review_state,
  normalize_review_decision,
  normalize_review_priority,
  sort_signals_by_review,
  summarize_reviews,
)


def main() -> int:
  errors: list[str] = []

  original_signal = {"id": "signal_001", "title": "A", "action": "Read Now", "score": 0.9}
  watch_signal = {"id": "signal_002", "title": "B", "action": "Watch", "score": 0.5}
  ignore_signal = {"id": "signal_003", "title": "C", "action": "Ignore", "score": 0.2}

  if default_review_state(original_signal)["review_decision"] != "採用":
    errors.append("Read Nowから採用初期値を作れません")
  if default_review_state(watch_signal)["review_decision"] != "保留":
    errors.append("Watchから保留初期値を作れません")
  if default_review_state(ignore_signal)["review_decision"] != "見送り":
    errors.append("Ignoreから見送り初期値を作れません")

  if normalize_review_decision("approve") != "採用":
    errors.append("英語review decisionの日本語化に失敗しました")
  if normalize_review_priority("low") != 3:
    errors.append("priority正規化に失敗しました")

  applied = apply_review_to_signal(
    original_signal,
    {
      "review_decision": "accept",
      "review_priority": "high",
      "review_comment": " 今週確認 ",
      "reviewed": "true",
    },
  )
  if applied["review"]["review_decision"] != "採用":
    errors.append("reviewをSignalへ反映できません")
  if original_signal.get("review") is not None:
    errors.append("元Signalを破壊しています")

  applied_many = apply_reviews_to_signals(
    [original_signal, watch_signal, ignore_signal],
    {
      "signal_002": {
        "review_decision": "hold",
        "review_priority": "2",
        "review_comment": "継続監視",
        "reviewed": True,
      }
    },
  )
  if len(applied_many) != 3 or applied_many[1]["review"]["review_decision"] != "保留":
    errors.append("複数Signalへのreview反映に失敗しました")

  summary = summarize_reviews(applied_many)
  if summary["合計"] != 3 or summary["保留"] < 1:
    errors.append("review summary生成に失敗しました")

  sorted_signals = sort_signals_by_review(
    [
      {**watch_signal, "review": {"review_decision": "保留", "review_priority": 2, "review_comment": "", "reviewed": True}},
      {**ignore_signal, "review": {"review_decision": "見送り", "review_priority": 3, "review_comment": "", "reviewed": True}},
      {**original_signal, "review": {"review_decision": "採用", "review_priority": 1, "review_comment": "", "reviewed": True}},
    ]
  )
  if sorted_signals[0]["id"] != "signal_001":
    errors.append("review順の並べ替えに失敗しました")

  if errors:
    print("[v9 review state readiness] NG:")
    for error in errors:
      print(f"- {error}")
    return 1

  print("[v9 review state readiness] OK: human review state core is ready.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
