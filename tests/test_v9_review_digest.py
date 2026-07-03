"""Tests for the v9 review-aware digest preview."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from services_v9.digest_export import (
  build_weekly_digest_markdown,
  select_confirmed_review_signals,
  select_review_aware_top_signals,
  signals_to_csv,
  signals_to_json,
  summarize_confirmed_reviews,
)
from services_v9.signal_models import Signal, WatchProfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PERSISTENCE_SOURCE = (PROJECT_ROOT / "services_v9" / "persistence.py").read_text(encoding="utf-8")
DIGEST_SOURCE = (PROJECT_ROOT / "services_v9" / "digest_export.py").read_text(encoding="utf-8")
APP_SOURCE = (PROJECT_ROOT / "ui_v9" / "signal_watch_app.py").read_text(encoding="utf-8")
TABS_SOURCE = (PROJECT_ROOT / "ui_v9" / "tabs.py").read_text(encoding="utf-8")


def _signal(
  signal_id: str,
  *,
  title: str,
  action: str = "Watch",
  score: float = 0.6,
  review: dict | None = None,
  signal_type: str = "patent",
) -> dict:
  signal = {
    "id": signal_id,
    "title": title,
    "type": signal_type,
    "source_url": f"https://example.com/{signal_id}",
    "source_name": "Demo Source",
    "published_date": "2026-07-04",
    "summary": "summary",
    "score": score,
    "previous_score": None,
    "status": "New",
    "action": action,
    "why_read": "w",
    "what_to_check": "c",
    "next_action": "n",
    "tags": [],
    "companies": [],
  }
  if review is not None:
    signal["review"] = review
  return signal


def _watch_profile() -> WatchProfile:
  return WatchProfile.from_dict({"schema_version": "v9.2"})


def test_can_count_confirmed_adopted_reviews() -> None:
  summary = summarize_confirmed_reviews([
    _signal("a", title="A", review={"review_decision": "採用", "review_priority": 1, "review_comment": "", "reviewed": True})
  ])
  assert summary["adopted_count"] == 1


def test_can_count_confirmed_hold_reviews() -> None:
  summary = summarize_confirmed_reviews([
    _signal("a", title="A", review={"review_decision": "保留", "review_priority": 2, "review_comment": "", "reviewed": True})
  ])
  assert summary["hold_count"] == 1


def test_can_count_confirmed_rejected_reviews() -> None:
  summary = summarize_confirmed_reviews([
    _signal("a", title="A", review={"review_decision": "見送り", "review_priority": 3, "review_comment": "", "reviewed": True})
  ])
  assert summary["rejected_count"] == 1


def test_unreviewed_values_are_not_in_confirmed_counts() -> None:
  summary = summarize_confirmed_reviews([
    _signal("a", title="A", review={"review_decision": "採用", "review_priority": 1, "review_comment": "", "reviewed": False})
  ])
  assert summary["adopted_count"] == 0
  assert summary["unreviewed_count"] == 1


def test_reviewless_signal_is_treated_as_unreviewed() -> None:
  summary = summarize_confirmed_reviews([_signal("a", title="A")])
  assert summary["unreviewed_count"] == 1


def test_confirmed_adopted_signals_are_prioritized_in_top3() -> None:
  signals = [
    _signal("a", title="A", score=0.95, action="Read Now", review={"review_decision": "採用", "review_priority": 1, "review_comment": "", "reviewed": True}),
    _signal("b", title="B", score=0.90, action="Read Now"),
  ]
  top_signals = select_review_aware_top_signals(signals, top_n=3)
  assert top_signals[0]["id"] == "a"


def test_priority_one_comes_before_priority_two() -> None:
  signals = [
    _signal("a", title="A", score=0.80, review={"review_decision": "採用", "review_priority": 2, "review_comment": "", "reviewed": True}),
    _signal("b", title="B", score=0.70, review={"review_decision": "採用", "review_priority": 1, "review_comment": "", "reviewed": True}),
  ]
  top_signals = select_review_aware_top_signals(signals, top_n=2)
  assert top_signals[0]["id"] == "b"


def test_same_priority_uses_score_descending() -> None:
  signals = [
    _signal("a", title="A", score=0.80, review={"review_decision": "採用", "review_priority": 1, "review_comment": "", "reviewed": True}),
    _signal("b", title="B", score=0.90, review={"review_decision": "採用", "review_priority": 1, "review_comment": "", "reviewed": True}),
  ]
  top_signals = select_review_aware_top_signals(signals, top_n=2)
  assert top_signals[0]["id"] == "b"


def test_rejected_signal_is_excluded_from_top3() -> None:
  signals = [
    _signal("a", title="A", score=0.95, action="Read Now", review={"review_decision": "見送り", "review_priority": 1, "review_comment": "", "reviewed": True}),
    _signal("b", title="B", score=0.70, action="Watch"),
  ]
  top_signals = select_review_aware_top_signals(signals, top_n=3)
  assert all(signal["id"] != "a" for signal in top_signals)


def test_unreviewed_signals_fill_when_adopted_are_less_than_three() -> None:
  signals = [
    _signal("a", title="A", score=0.95, action="Read Now", review={"review_decision": "採用", "review_priority": 1, "review_comment": "", "reviewed": True}),
    _signal("b", title="B", score=0.80, action="Read Now"),
    _signal("c", title="C", score=0.70, action="Watch"),
  ]
  top_signals = select_review_aware_top_signals(signals, top_n=3)
  assert [signal["id"] for signal in top_signals] == ["a", "b", "c"]


def test_confirmed_hold_fills_before_unreviewed() -> None:
  signals = [
    _signal("a", title="A", score=0.95, action="Read Now", review={"review_decision": "採用", "review_priority": 1, "review_comment": "", "reviewed": True}),
    _signal("b", title="B", score=0.60, action="Watch", review={"review_decision": "保留", "review_priority": 2, "review_comment": "", "reviewed": True}),
    _signal("c", title="C", score=0.90, action="Read Now"),
  ]
  top_signals = select_review_aware_top_signals(signals, top_n=3)
  assert [signal["id"] for signal in top_signals][:2] == ["a", "b"]


def test_top3_returns_at_most_three_signals() -> None:
  signals = [_signal(str(index), title=str(index), score=0.5 + index / 100) for index in range(5)]
  assert len(select_review_aware_top_signals(signals, top_n=3)) == 3


def test_two_signals_return_two_items() -> None:
  signals = [_signal("a", title="A"), _signal("b", title="B")]
  assert len(select_review_aware_top_signals(signals, top_n=3)) == 2


def test_empty_signal_list_does_not_fail() -> None:
  assert select_review_aware_top_signals([], top_n=3) == []


def test_does_not_mutate_original_signals() -> None:
  signals = [_signal("a", title="A")]
  original = deepcopy(signals)
  select_review_aware_top_signals(signals, top_n=3)
  assert signals == original


def test_digest_contains_human_review_status_section() -> None:
  digest = build_weekly_digest_markdown([Signal.from_dict(_signal("a", title="A"))], _watch_profile())
  assert "## 人間レビュー状況" in digest


def test_digest_contains_reviewed_text() -> None:
  digest = build_weekly_digest_markdown(
    [Signal.from_dict(_signal("a", title="A", review={"review_decision": "採用", "review_priority": 1, "review_comment": "", "reviewed": True}))],
    _watch_profile(),
    reviewed_signals=[_signal("a", title="A", review={"review_decision": "採用", "review_priority": 1, "review_comment": "", "reviewed": True})],
  )
  assert "レビュー済み" in digest


def test_digest_contains_unreviewed_text() -> None:
  digest = build_weekly_digest_markdown([Signal.from_dict(_signal("a", title="A"))], _watch_profile())
  assert "未レビュー" in digest


def test_digest_contains_system_action_text() -> None:
  digest = build_weekly_digest_markdown([Signal.from_dict(_signal("a", title="A", action="Read Now"))], _watch_profile())
  assert "システム判断" in digest


def test_digest_contains_human_review_text() -> None:
  digest = build_weekly_digest_markdown(
    [Signal.from_dict(_signal("a", title="A", review={"review_decision": "採用", "review_priority": 1, "review_comment": "", "reviewed": True}))],
    _watch_profile(),
    reviewed_signals=[_signal("a", title="A", review={"review_decision": "採用", "review_priority": 1, "review_comment": "", "reviewed": True})],
  )
  assert "人間レビュー" in digest


def test_digest_contains_review_comment() -> None:
  review = {"review_decision": "採用", "review_priority": 1, "review_comment": "今週読む", "reviewed": True}
  signal = _signal("a", title="A", review=review)
  digest = build_weekly_digest_markdown([Signal.from_dict(signal)], _watch_profile(), reviewed_signals=[signal])
  assert "レビューコメント: 今週読む" in digest


def test_unreviewed_signal_is_not_shown_as_human_adopted() -> None:
  signal = _signal("a", title="A", action="Read Now", review={"review_decision": "採用", "review_priority": 1, "review_comment": "", "reviewed": False})
  digest = build_weekly_digest_markdown([Signal.from_dict(signal)], _watch_profile(), reviewed_signals=[signal])
  assert "人間レビュー: 未レビュー" in digest


def test_rejected_signal_is_not_in_top3_body() -> None:
  reviewed = _signal("a", title="Rejected", action="Read Now", review={"review_decision": "見送り", "review_priority": 1, "review_comment": "", "reviewed": True})
  filler = _signal("b", title="Keep", action="Watch", score=0.70)
  digest = build_weekly_digest_markdown(
    [Signal.from_dict(reviewed), Signal.from_dict(filler)],
    _watch_profile(),
    reviewed_signals=[reviewed, filler],
  )
  assert "Rejected" not in digest.split("## 前回からの主な変化")[0]


def test_hold_signal_section_can_be_generated() -> None:
  hold = _signal("a", title="Hold", review={"review_decision": "保留", "review_priority": 2, "review_comment": "次回確認", "reviewed": True})
  digest = build_weekly_digest_markdown([Signal.from_dict(hold)], _watch_profile(), reviewed_signals=[hold])
  assert "## 継続監視するシグナル" in digest


def test_rejected_signal_section_can_be_generated() -> None:
  rejected = _signal("a", title="Reject", review={"review_decision": "見送り", "review_priority": 3, "review_comment": "対象外", "reviewed": True})
  digest = build_weekly_digest_markdown([Signal.from_dict(rejected)], _watch_profile(), reviewed_signals=[rejected])
  assert "## 今回見送ったシグナル" in digest


def test_digest_can_be_generated_for_signals_without_reviews() -> None:
  digest = build_weekly_digest_markdown([Signal.from_dict(_signal("a", title="A"))], _watch_profile())
  assert "## 今週まず読むべき3件" in digest


def test_csv_and_json_export_outputs_are_unchanged_by_review_logic() -> None:
  signal = Signal.from_dict(_signal("a", title="A"))
  csv_text = signals_to_csv([signal])
  json_text = signals_to_json([signal], _watch_profile())
  assert "review_decision" not in csv_text
  assert "\"review_decision\"" not in json_text


def test_snapshot_persistence_source_is_unchanged() -> None:
  assert "review_decision" not in PERSISTENCE_SOURCE
  assert "review_comment" not in PERSISTENCE_SOURCE


def test_digest_code_does_not_call_external_apis() -> None:
  combined_source = DIGEST_SOURCE + "\n" + APP_SOURCE + "\n" + TABS_SOURCE
  banned_tokens = [
    "import requests",
    "import httpx",
    "from openai",
    "google.generativeai",
    "WebSearch(",
    "CallMcpTool(",
  ]
  assert all(token not in combined_source for token in banned_tokens)


def test_can_select_confirmed_hold_signals() -> None:
  hold = _signal("a", title="Hold", review={"review_decision": "保留", "review_priority": 2, "review_comment": "", "reviewed": True})
  selected = select_confirmed_review_signals([hold], "保留", limit=10)
  assert selected[0]["id"] == "a"
