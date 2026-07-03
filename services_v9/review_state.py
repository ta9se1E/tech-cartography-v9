"""Pure human review state helpers for v9."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

REVIEW_DECISIONS = ["採用", "保留", "見送り"]

REVIEW_PRIORITIES = {
  1: "高",
  2: "中",
  3: "低",
}

_DECISION_ALIASES = {
  "採用": "採用",
  "accept": "採用",
  "accepted": "採用",
  "approve": "採用",
  "approved": "採用",
  "保留": "保留",
  "hold": "保留",
  "pending": "保留",
  "watch": "保留",
  "見送り": "見送り",
  "reject": "見送り",
  "rejected": "見送り",
  "ignore": "見送り",
  "skip": "見送り",
}

_PRIORITY_ALIASES = {
  "1": 1,
  "高": 1,
  "high": 1,
  "2": 2,
  "中": 2,
  "medium": 2,
  "3": 3,
  "低": 3,
  "low": 3,
}

_ACTION_TO_REVIEW = {
  "Read Now": ("採用", 1),
  "Watch": ("保留", 2),
  "Ignore": ("見送り", 3),
}

_TRUE_STRINGS = {"true", "1", "yes"}
_FALSE_STRINGS = {"false", "0", "no"}
_DECISION_ORDER = {"採用": 0, "保留": 1, "見送り": 2}


def _coerce_bool(value: Any) -> bool:
  if isinstance(value, bool):
    return value
  if isinstance(value, str):
    normalized = value.strip().lower()
    if normalized in _TRUE_STRINGS:
      return True
    if normalized in _FALSE_STRINGS:
      return False
  return bool(value)


def _safe_score(value: Any) -> float:
  try:
    return float(value)
  except (TypeError, ValueError):
    return 0.0


def normalize_review_decision(value: Any) -> str:
  normalized = str(value or "").strip()
  if not normalized:
    return "保留"
  return _DECISION_ALIASES.get(normalized.lower(), _DECISION_ALIASES.get(normalized, "保留"))


def normalize_review_priority(value: Any) -> int:
  if value in {1, 2, 3}:
    return int(value)
  normalized = str(value or "").strip()
  if not normalized:
    return 2
  return _PRIORITY_ALIASES.get(normalized.lower(), _PRIORITY_ALIASES.get(normalized, 2))


def default_review_state(signal: dict[str, Any]) -> dict[str, Any]:
  decision, priority = _ACTION_TO_REVIEW.get(str(signal.get("action", "") or "").strip(), ("保留", 2))
  return {
    "review_decision": decision,
    "review_priority": priority,
    "review_comment": "",
    "reviewed": False,
  }


def normalize_review_state(review: dict[str, Any] | None) -> dict[str, Any]:
  raw = review or {}
  return {
    "review_decision": normalize_review_decision(raw.get("review_decision")),
    "review_priority": normalize_review_priority(raw.get("review_priority")),
    "review_comment": str(raw.get("review_comment", "") or "").strip(),
    "reviewed": _coerce_bool(raw.get("reviewed", False)),
  }


def apply_review_to_signal(
  signal: dict[str, Any],
  review: dict[str, Any],
) -> dict[str, Any]:
  copied_signal = deepcopy(signal)
  copied_signal["review"] = normalize_review_state(review)
  return copied_signal


def apply_reviews_to_signals(
  signals: list[dict[str, Any]],
  reviews_by_signal_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
  applied: list[dict[str, Any]] = []
  for signal in signals:
    signal_id = str(signal.get("id", "") or "").strip()
    if signal_id and signal_id in reviews_by_signal_id:
      applied.append(apply_review_to_signal(signal, reviews_by_signal_id[signal_id]))
      continue
    if signal_id and isinstance(signal.get("review"), dict):
      applied.append(apply_review_to_signal(signal, dict(signal["review"])))
      continue
    applied.append(apply_review_to_signal(signal, default_review_state(signal)))
  return applied


def summarize_reviews(signals: list[dict[str, Any]]) -> dict[str, int]:
  summary = {
    "採用": 0,
    "保留": 0,
    "見送り": 0,
    "未レビュー": 0,
    "合計": 0,
  }
  for signal in signals:
    if isinstance(signal.get("review"), dict):
      review = normalize_review_state(signal.get("review"))
    else:
      review = default_review_state(signal)
    summary[review["review_decision"]] += 1
    if not review["reviewed"]:
      summary["未レビュー"] += 1
    summary["合計"] += 1
  return summary


def sort_signals_by_review(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
  def sort_key(signal: dict[str, Any]) -> tuple[int, int, int, float, str]:
    if isinstance(signal.get("review"), dict):
      review = normalize_review_state(signal.get("review"))
    else:
      review = default_review_state(signal)
    return (
      _DECISION_ORDER.get(review["review_decision"], 1),
      review["review_priority"],
      0 if review["reviewed"] else 1,
      -_safe_score(signal.get("score")),
      str(signal.get("title", "") or ""),
    )

  return [deepcopy(signal) for signal in sorted(signals, key=sort_key)]
