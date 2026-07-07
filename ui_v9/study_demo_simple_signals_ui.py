"""Simple Mode signals tab for Study Demo."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import streamlit as st

from services_v9.signal_scoring import select_top_reads
from services_v9.study_demo_ui_mode import should_show_full_signal_details
from services_v9.signal_models import Signal
from ui_v9.labels import action_label_ja, type_label_ja
from ui_v9.study_demo_compact_components import render_signal_card_simple


def _signal_lookup_key(signal: Signal | Mapping[str, Any]) -> str:
  if isinstance(signal, Signal):
    return f"{signal.type}:{signal.title}:{signal.source_name}"
  return f"{signal.get('type', '')}:{signal.get('title', '')}:{signal.get('source_name', '')}"


def _has_meaningful_status_variation(signals: Sequence[Signal]) -> bool:
  statuses = {signal.status for signal in signals}
  return len(statuses - {"Stable"}) > 0


def filter_signals_for_simple_display(
  signals: Sequence[Signal],
  *,
  hide_empty_titles: bool = True,
) -> tuple[list[Signal], int]:
  visible: list[Signal] = []
  hidden_empty = 0
  for signal in signals:
    title = str(signal.title or "").strip()
    if hide_empty_titles and not title:
      hidden_empty += 1
      continue
    visible.append(signal)
  return visible, hidden_empty


def split_top_and_remaining(
  signals: Sequence[Signal],
  *,
  top_n: int = 3,
) -> tuple[list[Signal], list[Signal]]:
  visible, _ = filter_signals_for_simple_display(signals)
  top_reads = select_top_reads(visible, limit=top_n)
  if len(top_reads) < top_n and len(visible) >= top_n:
    top_reads = visible[:top_n]
  top_keys = {_signal_lookup_key(item) for item in top_reads}
  remaining = [item for item in visible if _signal_lookup_key(item) not in top_keys]
  return top_reads, remaining


def render_simple_signals_tab(
  *,
  signals: Sequence[Signal],
  display_signals: Sequence[Mapping[str, Any]],
  source_info: Mapping[str, object],
) -> dict[str, bool]:
  display_signal_lookup = {
    _signal_lookup_key(Signal.from_dict(item) if "type" in item else item): item
    for item in display_signals
    if isinstance(item, dict)
  }
  score_explanation_lookup: dict[str, Mapping[str, Any]] = {}
  for item in display_signals:
    if not isinstance(item, dict):
      continue
    key = _signal_lookup_key(item)
    explanation = dict(item.get("score_explanation", {}) or {})
    if explanation:
      score_explanation_lookup[key] = explanation

  visible_signals, hidden_empty = filter_signals_for_simple_display(signals)
  top_reads, remaining = split_top_and_remaining(visible_signals)

  active_context = dict(source_info.get("active_context", {}) or {})
  run_id = str(active_context.get("active_search_run_id", "") or "")

  st.markdown("#### 今週まず読むべき3件")
  if not top_reads:
    st.info("今週優先して読む候補はまだありません。")
  else:
    columns = st.columns(len(top_reads))
    for column, signal in zip(columns, top_reads):
      with column:
        key = _signal_lookup_key(signal)
        render_signal_card_simple(
          signal=signal,
          display_signal=display_signal_lookup.get(key, {}),
          explanation=score_explanation_lookup.get(key, {}),
          search_run_id=run_id,
          key_namespace="simple_top3",
          index=0,
        )

  if hidden_empty:
    st.caption(f"表示対象 {len(visible_signals)}件 | タイトル未取得 {hidden_empty}件")

  available_types = sorted({signal.type for signal in visible_signals})
  available_actions = ["Read Now", "Watch", "Ignore"]
  filter_left, filter_mid, filter_right = st.columns(3)
  with filter_left:
    selected_types = st.multiselect(
      "種別",
      available_types,
      default=available_types,
      format_func=type_label_ja,
      key="ui_simple_type_filter",
    )
  with filter_mid:
    selected_tiers = st.multiselect(
      "Tier",
      options=sorted({str(display_signal_lookup.get(_signal_lookup_key(s), {}).get("relevance_tier", "")) for s in visible_signals if display_signal_lookup.get(_signal_lookup_key(s), {}).get("relevance_tier")}),
      default=sorted({str(display_signal_lookup.get(_signal_lookup_key(s), {}).get("relevance_tier", "")) for s in visible_signals if display_signal_lookup.get(_signal_lookup_key(s), {}).get("relevance_tier")}),
      key="ui_simple_tier_filter",
    )
  with filter_right:
    selected_actions = st.multiselect(
      "判断",
      available_actions,
      default=available_actions,
      format_func=action_label_ja,
      key="ui_simple_action_filter",
    )

  if should_show_full_signal_details() and _has_meaningful_status_variation(visible_signals):
    st.multiselect(
      "変化",
      ["New", "Rising", "Dropped", "Stable"],
      default=["New", "Rising", "Dropped", "Stable"],
      key="ui_simple_status_filter",
    )

  filtered_remaining = []
  for signal in remaining:
    key = _signal_lookup_key(signal)
    display_signal = display_signal_lookup.get(key, {})
    tier = str(display_signal.get("relevance_tier", "") or "")
    if signal.type not in selected_types:
      continue
    if selected_tiers and tier and tier not in selected_tiers:
      continue
    if signal.action not in selected_actions:
      continue
    filtered_remaining.append(signal)

  if filtered_remaining:
    with st.expander(f"残り{len(filtered_remaining)}件を見る", expanded=False):
      for index, signal in enumerate(filtered_remaining, start=1):
        key = _signal_lookup_key(signal)
        render_signal_card_simple(
          signal=signal,
          display_signal=display_signal_lookup.get(key, {}),
          explanation=score_explanation_lookup.get(key, {}),
          search_run_id=run_id,
          key_namespace="simple_remaining",
          index=index,
        )

  return {"save_snapshot": False}


__all__ = [
  "filter_signals_for_simple_display",
  "render_simple_signals_tab",
  "split_top_and_remaining",
]
