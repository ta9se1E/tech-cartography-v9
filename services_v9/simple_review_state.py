"""Simple Mode review state helpers."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

DECISION_UNREVIEWED = "unreviewed"
DECISION_ACCEPT = "accept"
DECISION_HOLD = "hold"
DECISION_REJECT = "reject"

SIMPLE_REVIEW_LABELS = {
  DECISION_UNREVIEWED: "未判断",
  DECISION_ACCEPT: "関連",
  DECISION_HOLD: "保留",
  DECISION_REJECT: "除外",
}

SIMPLE_REVIEW_OPTIONS = (
  (DECISION_UNREVIEWED, "未判断"),
  (DECISION_ACCEPT, "関連"),
  (DECISION_HOLD, "保留"),
  (DECISION_REJECT, "除外"),
)


def normalize_simple_decision(value: Any) -> str:
  text = str(value or "").strip().lower()
  if text in {"", "unreviewed", "未判断", "none"}:
    return DECISION_UNREVIEWED
  if text in {"accept", "accepted", "採用", "関連"}:
    return DECISION_ACCEPT
  if text in {"hold", "pending", "保留"}:
    return DECISION_HOLD
  if text in {"reject", "rejected", "見送り", "除外"}:
    return DECISION_REJECT
  return DECISION_UNREVIEWED


def is_saved_review(record: Mapping[str, Any] | None) -> bool:
  if not record:
    return False
  if not (record.get("reviewed") or record.get("reviewed_at")):
    return False
  return normalize_simple_decision(record.get("decision", record.get("review_decision", ""))) != DECISION_UNREVIEWED


def can_save_review(decision: str) -> bool:
  return normalize_simple_decision(decision) != DECISION_UNREVIEWED


def save_review_blocked_message() -> str:
  return "関連・保留・除外のいずれかを選択してください。"


def summarize_simple_reviews(
  reviews: Sequence[Mapping[str, Any]],
  signal_ids: Sequence[str],
) -> dict[str, int]:
  by_id = {str(item.get("signal_id", "")): item for item in reviews}
  summary = {"unreviewed": 0, "accept": 0, "hold": 0, "reject": 0}
  for signal_id in signal_ids:
    item = by_id.get(str(signal_id))
    if not is_saved_review(item):
      summary["unreviewed"] += 1
      continue
    decision = normalize_simple_decision(item.get("decision", item.get("review_decision", "")))
    if decision in summary:
      summary[decision] += 1
    else:
      summary["unreviewed"] += 1
  return summary


def to_backend_decision(decision: str) -> str | None:
  normalized = normalize_simple_decision(decision)
  if normalized == DECISION_UNREVIEWED:
    return None
  return normalized


__all__ = [
  "DECISION_UNREVIEWED",
  "SIMPLE_REVIEW_OPTIONS",
  "can_save_review",
  "is_saved_review",
  "normalize_simple_decision",
  "save_review_blocked_message",
  "summarize_simple_reviews",
  "to_backend_decision",
]
