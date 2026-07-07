"""Single source of truth for initial baseline vs comparable run state."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _lineage_key(context: Mapping[str, Any]) -> tuple[str, ...]:
  return (
    str(context.get("source_theme_id", "") or ""),
    str(context.get("source_watch_profile_id", "") or ""),
    str(context.get("source_search_plan_id", "") or ""),
  )


def _is_comparable_previous(
  previous: Mapping[str, Any],
  *,
  current_run_id: str,
  context: Mapping[str, Any],
) -> bool:
  previous_run_id = str(previous.get("source_run_id", "") or previous.get("search_run_id", "") or "")
  if not previous_run_id or previous_run_id == current_run_id:
    return False
  if str(previous.get("comparison_status", "") or "") == "not_comparable":
    return False
  previous_lineage = (
    str(previous.get("source_theme_id", "") or ""),
    str(previous.get("source_watch_profile_id", "") or ""),
    str(previous.get("source_search_plan_id", "") or ""),
  )
  if any(previous_lineage) and previous_lineage != _lineage_key(context):
    return False
  return True


def resolve_run_baseline_state(
  current_run: Mapping[str, Any],
  previous_run: Mapping[str, Any] | None = None,
  *,
  snapshots: Sequence[Mapping[str, Any]] | None = None,
  weekly_state: Mapping[str, Any] | None = None,
  integrated_count: int = 0,
  priority_count: int = 3,
) -> dict[str, Any]:
  context = dict(current_run or {})
  current_run_id = str(context.get("active_search_run_id", "") or context.get("search_run_id", "") or "")
  weekly = dict(weekly_state or {})
  if str(weekly.get("comparison_status", "") or "") == "not_comparable":
    return _initial_payload(
      current_count=integrated_count,
      priority_count=priority_count,
      reason="diff_not_comparable",
    )
  if bool(context.get("baseline")):
    return _initial_payload(
      current_count=integrated_count,
      priority_count=priority_count,
      reason="run_metadata_baseline",
    )

  comparable_previous: Mapping[str, Any] | None = None
  if previous_run and _is_comparable_previous(previous_run, current_run_id=current_run_id, context=context):
    comparable_previous = previous_run
  else:
    for snapshot in list(snapshots or []):
      candidate = {
        "source_run_id": snapshot.get("source_run_id"),
        "source_theme_id": context.get("source_theme_id"),
        "source_watch_profile_id": context.get("source_watch_profile_id"),
        "source_search_plan_id": context.get("source_search_plan_id"),
      }
      if _is_comparable_previous(candidate, current_run_id=current_run_id, context=context):
        comparable_previous = candidate
        break

  if comparable_previous:
    diff = dict(weekly.get("diff", {}) or {})
    return {
      "state": "comparable",
      "has_comparison": True,
      "comparison_run_id": str(
        comparable_previous.get("source_run_id", "") or comparable_previous.get("search_run_id", "") or ""
      ),
      "current_count": integrated_count,
      "priority_count": priority_count,
      "message": "",
      "next_message": "",
      "diff": diff or None,
      "show_diff_counts": bool(diff),
    }

  return _initial_payload(
    current_count=integrated_count,
    priority_count=priority_count,
    reason="no_comparable_previous_run",
  )


def _initial_payload(*, current_count: int, priority_count: int, reason: str) -> dict[str, Any]:
  return {
    "state": "initial_baseline",
    "has_comparison": False,
    "comparison_run_id": None,
    "current_count": current_count,
    "priority_count": priority_count,
    "message": "初回ベースラインを保存しました",
    "next_message": "次回Run以降、新規・順位変化・除外候補を表示します。",
    "diff": None,
    "show_diff_counts": False,
    "reason": reason,
  }


def is_initial_baseline(state: Mapping[str, Any]) -> bool:
  return str(state.get("state", "") or "") == "initial_baseline"


def build_baseline_summary(state: Mapping[str, Any]) -> dict[str, Any]:
  if is_initial_baseline(state):
    return {
      "headline": "初回ベースラインを保存しました",
      "current_count": int(state.get("current_count", 0) or 0),
      "priority_count": int(state.get("priority_count", 3) or 3),
      "comparison_label": "なし",
      "next_message": str(state.get("next_message", "") or ""),
      "show_diff_counts": False,
    }
  diff = dict(state.get("diff", {}) or {})
  counts = dict(diff.get("counts", {}) or {})
  return {
    "headline": "前回Runからの変化",
    "current_count": int(state.get("current_count", 0) or 0),
    "priority_count": int(state.get("priority_count", 3) or 3),
    "comparison_label": str(state.get("comparison_run_id", "") or "あり"),
    "next_message": "",
    "show_diff_counts": True,
    "counts": counts,
  }


def build_change_labels(
  *,
  baseline_state: Mapping[str, Any],
  signal_status: str = "",
) -> str | None:
  if is_initial_baseline(baseline_state):
    return "初回候補"
  mapping = {
    "New": "新規",
    "Rising": "順位上昇",
    "Dropped": "順位低下",
    "Stable": "継続",
  }
  return mapping.get(str(signal_status or ""), None)


__all__ = [
  "build_baseline_summary",
  "build_change_labels",
  "is_initial_baseline",
  "resolve_run_baseline_state",
]
