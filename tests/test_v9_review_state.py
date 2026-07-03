"""Tests for the v9 human review state core."""

from __future__ import annotations

from copy import deepcopy

from services_v9.review_state import (
  REVIEW_DECISIONS,
  REVIEW_PRIORITIES,
  apply_review_to_signal,
  apply_reviews_to_signals,
  default_review_state,
  normalize_review_decision,
  normalize_review_priority,
  normalize_review_state,
  sort_signals_by_review,
  summarize_reviews,
)


def _signal(signal_id: str = "signal_001", **overrides) -> dict:
  signal = {
    "id": signal_id,
    "title": f"title-{signal_id}",
    "action": "Watch",
    "score": 0.6,
  }
  signal.update(overrides)
  return signal


def test_review_decisions_include_expected_values() -> None:
  assert REVIEW_DECISIONS == ["採用", "保留", "見送り"]


def test_review_priorities_include_expected_values() -> None:
  assert REVIEW_PRIORITIES == {1: "高", 2: "中", 3: "低"}


def test_normalize_review_decision_keeps_adopt() -> None:
  assert normalize_review_decision("採用") == "採用"


def test_normalize_review_decision_maps_accept() -> None:
  assert normalize_review_decision("accept") == "採用"


def test_normalize_review_decision_maps_hold() -> None:
  assert normalize_review_decision("hold") == "保留"


def test_normalize_review_decision_maps_ignore() -> None:
  assert normalize_review_decision("ignore") == "見送り"


def test_normalize_review_decision_defaults_unknown_to_hold() -> None:
  assert normalize_review_decision("unknown") == "保留"


def test_normalize_review_priority_maps_high_japanese() -> None:
  assert normalize_review_priority("高") == 1


def test_normalize_review_priority_maps_medium() -> None:
  assert normalize_review_priority("medium") == 2


def test_normalize_review_priority_maps_low() -> None:
  assert normalize_review_priority("low") == 3


def test_normalize_review_priority_defaults_unknown_to_two() -> None:
  assert normalize_review_priority("unknown") == 2


def test_default_review_state_from_read_now() -> None:
  review = default_review_state(_signal(action="Read Now"))
  assert review["review_decision"] == "採用"
  assert review["review_priority"] == 1


def test_default_review_state_from_watch() -> None:
  review = default_review_state(_signal(action="Watch"))
  assert review["review_decision"] == "保留"
  assert review["review_priority"] == 2


def test_default_review_state_from_ignore() -> None:
  review = default_review_state(_signal(action="Ignore"))
  assert review["review_decision"] == "見送り"
  assert review["review_priority"] == 3


def test_default_review_state_is_unreviewed() -> None:
  assert default_review_state(_signal())["reviewed"] is False


def test_default_review_state_handles_unknown_action() -> None:
  review = default_review_state(_signal(action="Other"))
  assert review["review_decision"] == "保留"
  assert review["review_priority"] == 2


def test_normalize_review_state_fills_missing_keys() -> None:
  review = normalize_review_state({"review_decision": "accept"})
  assert review == {
    "review_decision": "採用",
    "review_priority": 2,
    "review_comment": "",
    "reviewed": False,
  }


def test_normalize_review_state_trims_comment() -> None:
  review = normalize_review_state({"review_comment": " 今週確認する "})
  assert review["review_comment"] == "今週確認する"


def test_normalize_review_state_parses_true_string() -> None:
  review = normalize_review_state({"reviewed": "true"})
  assert review["reviewed"] is True


def test_normalize_review_state_parses_false_string() -> None:
  review = normalize_review_state({"reviewed": "false"})
  assert review["reviewed"] is False


def test_apply_review_to_signal_attaches_review() -> None:
  applied = apply_review_to_signal(_signal(), {"review_decision": "accept"})
  assert applied["review"]["review_decision"] == "採用"


def test_apply_review_to_signal_keeps_action() -> None:
  applied = apply_review_to_signal(_signal(action="Read Now"), {"review_decision": "hold"})
  assert applied["action"] == "Read Now"


def test_apply_review_to_signal_does_not_mutate_original() -> None:
  signal = _signal()
  original = deepcopy(signal)
  applied = apply_review_to_signal(signal, {"review_decision": "accept"})
  assert signal == original
  assert "review" not in signal
  assert "review" in applied


def test_apply_reviews_to_signals_handles_multiple_signals() -> None:
  signals = [_signal("signal_001"), _signal("signal_002")]
  applied = apply_reviews_to_signals(signals, {"signal_001": {"review_decision": "accept", "reviewed": True}})
  assert applied[0]["review"]["review_decision"] == "採用"
  assert applied[1]["review"]["review_decision"] == "保留"


def test_apply_reviews_to_signals_adds_default_review_when_missing() -> None:
  applied = apply_reviews_to_signals([_signal(action="Ignore")], {})
  assert applied[0]["review"]["review_decision"] == "見送り"


def test_apply_reviews_to_signals_handles_signal_without_id() -> None:
  signal = _signal(signal_id="", title="no-id")
  signal.pop("id")
  applied = apply_reviews_to_signals([signal], {"signal_001": {"review_decision": "accept"}})
  assert applied[0]["review"]["review_decision"] == "保留"


def test_summarize_reviews_counts_adopted() -> None:
  signals = [
    _signal(action="Read Now", review={"review_decision": "採用", "review_priority": 1, "review_comment": "", "reviewed": True})
  ]
  assert summarize_reviews(signals)["採用"] == 1


def test_summarize_reviews_counts_hold() -> None:
  signals = [
    _signal(action="Watch", review={"review_decision": "保留", "review_priority": 2, "review_comment": "", "reviewed": True})
  ]
  assert summarize_reviews(signals)["保留"] == 1


def test_summarize_reviews_counts_rejected() -> None:
  signals = [
    _signal(action="Ignore", review={"review_decision": "見送り", "review_priority": 3, "review_comment": "", "reviewed": True})
  ]
  assert summarize_reviews(signals)["見送り"] == 1


def test_summarize_reviews_counts_unreviewed() -> None:
  signals = [_signal(action="Watch")]
  assert summarize_reviews(signals)["未レビュー"] == 1


def test_summarize_reviews_counts_total() -> None:
  signals = [_signal("signal_001"), _signal("signal_002")]
  assert summarize_reviews(signals)["合計"] == 2


def test_summarize_reviews_empty_list_is_zero() -> None:
  assert summarize_reviews([]) == {"採用": 0, "保留": 0, "見送り": 0, "未レビュー": 0, "合計": 0}


def test_sort_signals_by_review_places_adopted_first() -> None:
  signals = [
    _signal("signal_001", review={"review_decision": "保留", "review_priority": 2, "review_comment": "", "reviewed": True}),
    _signal("signal_002", review={"review_decision": "採用", "review_priority": 2, "review_comment": "", "reviewed": True}),
  ]
  sorted_signals = sort_signals_by_review(signals)
  assert sorted_signals[0]["id"] == "signal_002"


def test_sort_signals_by_review_places_priority_one_first_within_adopted() -> None:
  signals = [
    _signal("signal_001", review={"review_decision": "採用", "review_priority": 2, "review_comment": "", "reviewed": True}),
    _signal("signal_002", review={"review_decision": "採用", "review_priority": 1, "review_comment": "", "reviewed": True}),
  ]
  sorted_signals = sort_signals_by_review(signals)
  assert sorted_signals[0]["id"] == "signal_002"


def test_sort_signals_by_review_places_higher_score_first_when_otherwise_equal() -> None:
  signals = [
    _signal("signal_001", score=0.7, review={"review_decision": "採用", "review_priority": 1, "review_comment": "", "reviewed": True}),
    _signal("signal_002", score=0.9, review={"review_decision": "採用", "review_priority": 1, "review_comment": "", "reviewed": True}),
  ]
  sorted_signals = sort_signals_by_review(signals)
  assert sorted_signals[0]["id"] == "signal_002"


def test_sort_signals_by_review_does_not_mutate_original() -> None:
  signals = [
    _signal("signal_001", review={"review_decision": "保留", "review_priority": 2, "review_comment": "", "reviewed": True}),
    _signal("signal_002", review={"review_decision": "採用", "review_priority": 1, "review_comment": "", "reviewed": True}),
  ]
  original = deepcopy(signals)
  sorted_signals = sort_signals_by_review(signals)
  assert signals == original
  assert sorted_signals[0]["id"] == "signal_002"
