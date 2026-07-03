"""Snapshot comparison helpers for Tech Cartography v9."""

from __future__ import annotations

from copy import deepcopy

from .signal_scoring import classify_action


def index_signals_by_id(signals: list[dict]) -> dict[str, dict]:
  return {
    str(signal.get("id", "")).strip(): deepcopy(signal)
    for signal in signals
    if str(signal.get("id", "")).strip()
  }


def _classify_from_snapshot(score: float, previous_score: float | None) -> str:
  if previous_score is None:
    return "New"
  delta = score - previous_score
  if delta >= 0.10:
    return "Rising"
  if delta <= -0.10:
    return "Dropped"
  return "Stable"


def apply_snapshot_status(current_signals: list[dict], previous_signals: list[dict]) -> list[dict]:
  previous_index = index_signals_by_id(previous_signals)
  updated: list[dict] = []
  for signal in current_signals:
    record = deepcopy(signal)
    previous = previous_index.get(str(record.get("id", "")).strip())
    previous_score = None if previous is None else previous.get("score")
    if previous_score is not None:
      previous_score = float(previous_score)
    record["previous_score"] = previous_score
    status = _classify_from_snapshot(float(record.get("score", 0.0)), previous_score)
    record["status"] = status
    record["action"] = classify_action(float(record.get("score", 0.0)), status)
    updated.append(record)
  return updated


def compare_snapshots(previous_signals: list[dict], current_signals: list[dict]) -> dict:
  previous_index = index_signals_by_id(previous_signals)
  current_with_status = apply_snapshot_status(current_signals, previous_signals)
  buckets = {
    "New": [],
    "Rising": [],
    "Dropped": [],
    "Stable": [],
  }
  for signal in current_with_status:
    buckets.setdefault(str(signal.get("status", "Stable")), []).append(signal)

  current_ids = {str(signal.get("id", "")).strip() for signal in current_signals}
  missing_signals: list[dict] = []
  for signal_id, previous in previous_index.items():
    if signal_id in current_ids:
      continue
    dropped = deepcopy(previous)
    dropped["status"] = "Dropped"
    dropped["action"] = classify_action(float(dropped.get("score", 0.0)), "Dropped")
    dropped["previous_score"] = previous.get("score")
    dropped["dropped_from_current"] = True
    missing_signals.append(dropped)
  buckets["Dropped"].extend(missing_signals)

  diff = {
    "current_signals": current_with_status,
    "missing_signals": missing_signals,
    "buckets": buckets,
    "counts": {
      "New": len(buckets["New"]),
      "Rising": len(buckets["Rising"]),
      "Dropped": len(buckets["Dropped"]),
      "Stable": len(buckets["Stable"]),
    },
  }
  diff["summary"] = summarize_diff(diff)
  return diff


def summarize_diff(diff: dict) -> str:
  counts = diff.get("counts", {})
  return (
    "前回と比較して、"
    f"新規{counts.get('New', 0)}件、"
    f"注目度上昇{counts.get('Rising', 0)}件、"
    f"注目度低下{counts.get('Dropped', 0)}件、"
    f"継続監視{counts.get('Stable', 0)}件が見つかりました。"
  )
