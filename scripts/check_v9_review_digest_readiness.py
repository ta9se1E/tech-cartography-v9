"""Readiness checks for the v9 review-aware digest preview."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.digest_export import (  # noqa: E402
  build_weekly_digest_markdown,
  select_review_aware_top_signals,
  select_confirmed_review_signals,
  summarize_confirmed_reviews,
)
from services_v9.signal_models import Signal, WatchProfile  # noqa: E402


def main() -> int:
  errors: list[str] = []

  watch_profile = WatchProfile.from_dict({"schema_version": "v9.2"})
  signals = [
    {
      "id": "sig-1",
      "title": "Adopted first",
      "type": "patent",
      "source_url": "https://example.com/1",
      "source_name": "Demo",
      "published_date": "2026-07-04",
      "summary": "summary",
      "score": 0.91,
      "previous_score": None,
      "status": "New",
      "action": "Read Now",
      "why_read": "w",
      "what_to_check": "c",
      "next_action": "n",
      "tags": [],
      "companies": [],
      "review": {"review_decision": "採用", "review_priority": 1, "review_comment": "今週読む", "reviewed": True},
    },
    {
      "id": "sig-2",
      "title": "Rejected",
      "type": "paper",
      "source_url": "https://example.com/2",
      "source_name": "Demo",
      "published_date": "2026-07-03",
      "summary": "summary",
      "score": 0.88,
      "previous_score": None,
      "status": "New",
      "action": "Read Now",
      "why_read": "w",
      "what_to_check": "c",
      "next_action": "n",
      "tags": [],
      "companies": [],
      "review": {"review_decision": "見送り", "review_priority": 3, "review_comment": "対象外", "reviewed": True},
    },
    {
      "id": "sig-3",
      "title": "Hold",
      "type": "web",
      "source_url": "https://example.com/3",
      "source_name": "Demo",
      "published_date": "2026-07-02",
      "summary": "summary",
      "score": 0.70,
      "previous_score": None,
      "status": "Stable",
      "action": "Watch",
      "why_read": "w",
      "what_to_check": "c",
      "next_action": "n",
      "tags": [],
      "companies": [],
      "review": {"review_decision": "保留", "review_priority": 2, "review_comment": "継続監視", "reviewed": True},
    },
    {
      "id": "sig-4",
      "title": "Unread read now",
      "type": "company",
      "source_url": "https://example.com/4",
      "source_name": "Demo",
      "published_date": "2026-07-01",
      "summary": "summary",
      "score": 0.83,
      "previous_score": None,
      "status": "New",
      "action": "Read Now",
      "why_read": "w",
      "what_to_check": "c",
      "next_action": "n",
      "tags": [],
      "companies": [],
    },
  ]

  summary = summarize_confirmed_reviews(signals)
  if summary["adopted_count"] != 1:
    errors.append("reviewed=Trueの採用件数を集計できません")
  if summary["hold_count"] != 1:
    errors.append("reviewed=Trueの保留件数を集計できません")
  if summary["rejected_count"] != 1:
    errors.append("reviewed=Trueの見送り件数を集計できません")
  if summary["unreviewed_count"] != 1:
    errors.append("reviewed=Falseを人間判断件数に含めず未レビューとして扱えません")

  top_signals = select_review_aware_top_signals(signals, top_n=3)
  top_titles = [signal["title"] for signal in top_signals]
  if top_titles[0] != "Adopted first":
    errors.append("採用SignalをTop3で優先できません")
  if "Rejected" in top_titles:
    errors.append("見送りSignalをTop3から除外できません")
  if "Unread read now" not in top_titles:
    errors.append("採用が3件未満の場合に未レビューSignalで補完できません")

  hold_signals = select_confirmed_review_signals(signals, "保留", limit=10)
  if not hold_signals or hold_signals[0]["title"] != "Hold":
    errors.append("保留Signalを抽出できません")

  markdown = build_weekly_digest_markdown(
    [Signal.from_dict(signal) for signal in signals],
    watch_profile,
    reviewed_signals=signals,
  )
  if "## 人間レビュー状況" not in markdown:
    errors.append("review-aware digestを生成できません")
  if "人間レビュー: 採用" not in markdown or "システム判断: 今すぐ読む" not in markdown:
    errors.append("人間レビューとシステム判断を併記できません")
  if "レビューコメント: 今週読む" not in markdown:
    errors.append("レビューコメントを表示できません")

  markdown_without_reviews = build_weekly_digest_markdown(
    [Signal.from_dict({k: v for k, v in signal.items() if k != "review"}) for signal in signals],
    watch_profile,
  )
  if "## 今週まず読むべき3件" not in markdown_without_reviews:
    errors.append("reviewがないSignalでもDigest生成できません")

  if errors:
    print("[v9 review digest readiness] NG:")
    for error in errors:
      print(f"- {error}")
    return 1

  print("[v9 review digest readiness] OK: review-aware digest preview is ready.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
