"""Simple Mode signals tab for Study Demo."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import streamlit as st

from services_v9.signal_models import Signal
from services_v9.simple_tier_display import TIER_WATCH, tier_display_label_ja
from services_v9.study_demo_ui_mode import should_show_full_signal_details
from ui_v9.study_demo_research_value_ui import (
  build_research_value_bundle,
  is_initial_baseline_run,
  render_research_value_card,
)
from ui_v9.study_demo_simple_signal_cards import render_tier_signal_card_simple


def _signal_lookup_key(signal: Signal | Mapping[str, Any]) -> str:
  if isinstance(signal, Signal):
    return f"{signal.type}:{signal.title}:{signal.source_name}"
  return f"{signal.get('type', '')}:{signal.get('title', '')}:{signal.get('source_name', '')}"


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
  top_reads = visible[:top_n]
  top_keys = {_signal_lookup_key(item) for item in top_reads}
  remaining = [item for item in visible if _signal_lookup_key(item) not in top_keys]
  return top_reads, remaining


def _tier_for_signal(display_signal: Mapping[str, Any]) -> str:
  return str(display_signal.get("relevance_tier", "") or display_signal.get("study_demo", {}).get("relevance_tier", "") or "D")


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

  visible_signals, hidden_empty = filter_signals_for_simple_display(signals)
  _, remaining = split_top_and_remaining(visible_signals)

  active_context = dict(source_info.get("active_context", {}) or {})
  run_id = str(active_context.get("active_search_run_id", "") or "")
  initial_baseline = is_initial_baseline_run(source_info)
  research_bundle = build_research_value_bundle(display_signals=display_signals, source_info=source_info, limit=3)
  research_items = list(research_bundle.get("items", []) or [])

  header_left, header_right = st.columns([3, 1])
  with header_left:
    st.markdown("#### 今回まず確認する3件")
  with header_right:
    if initial_baseline:
      st.markdown("**Initial Baseline**")
  st.caption(
    "タイトル・概要・監視条件に基づく優先確認候補です。技術的妥当性を示すものではありません。"
  )

  if not research_items:
    st.info("今回優先して確認する候補はまだありません。")
  else:
    research_lookup = {
      str(dict(item.get("signal", {}) or {}).get("signal_id", "")): item for item in research_items
    }
    research_title_lookup = {
      str(dict(item.get("signal", {}) or {}).get("title", "")): item for item in research_items
    }
    columns = st.columns(len(research_items))
    for column, item in zip(columns, research_items):
      with column:
        signal_payload = dict(item.get("signal", {}) or {})
        lookup_id = str(signal_payload.get("signal_id", "") or "")
        lookup_title = str(signal_payload.get("title", "") or "")
        display_signal = {}
        for candidate in display_signal_lookup.values():
          if str(candidate.get("id", "")) == lookup_id or str(candidate.get("title", "")) == lookup_title:
            display_signal = candidate
            break
        render_research_value_card(
          item=item,
          display_signal=display_signal,
          search_run_id=run_id,
          key_namespace="simple_top3",
          index=int(item.get("rank", 0) or 0),
          initial_baseline=initial_baseline,
        )
    top_keys = set(research_lookup.keys()) | set(research_title_lookup.keys())
    remaining = [
      signal
      for signal in remaining
      if str(display_signal_lookup.get(_signal_lookup_key(signal), {}).get("id", "")) not in top_keys
      and signal.title not in research_title_lookup
    ]

  if hidden_empty:
    st.caption(f"表示対象 {len(visible_signals)}件 | タイトル未取得 {hidden_empty}件")

  watch_remaining = []
  reference_low_remaining = []
  for signal in remaining:
    display_signal = display_signal_lookup.get(_signal_lookup_key(signal), {})
    tier = _tier_for_signal(display_signal)
    if tier == "B":
      watch_remaining.append(signal)
    elif tier in {"C", "D"}:
      reference_low_remaining.append(signal)

  if watch_remaining:
    st.markdown(f"#### 継続監視（{len(watch_remaining)}件）")
    for index, signal in enumerate(watch_remaining, start=1):
      key = _signal_lookup_key(signal)
      render_tier_signal_card_simple(
        signal=signal,
        display_signal=display_signal_lookup.get(key, {}),
        search_run_id=run_id,
        key_namespace="simple_watch",
        index=index,
      )

  if reference_low_remaining:
    with st.expander(f"参考・低優先 {len(reference_low_remaining)}件を見る", expanded=False):
      available_types = sorted({signal.type for signal in reference_low_remaining})
      available_tiers = sorted(
        {
          _tier_for_signal(display_signal_lookup.get(_signal_lookup_key(s), {}))
          for s in reference_low_remaining
          if _tier_for_signal(display_signal_lookup.get(_signal_lookup_key(s), {}))
        }
      )
      selected_types: list[str] = []
      selected_tiers: list[str] = []
      if available_types:
        selected_types = st.multiselect(
          "種別",
          available_types,
          default=[],
          format_func=lambda value: {"patent": "特許", "paper": "論文", "web": "Web情報"}.get(value, value),
          key="ui_simple_type_filter",
          placeholder="すべて表示",
        )
      if available_tiers:
        selected_tiers = st.multiselect(
          "Tier",
          options=available_tiers,
          default=[],
          format_func=tier_display_label_ja,
          key="ui_simple_tier_filter",
          placeholder="すべて表示",
        )
      filtered_reference = []
      for signal in reference_low_remaining:
        key = _signal_lookup_key(signal)
        display_signal = display_signal_lookup.get(key, {})
        tier = _tier_for_signal(display_signal)
        if selected_types and signal.type not in selected_types:
          continue
        if selected_tiers and tier not in selected_tiers:
          continue
        filtered_reference.append(signal)
      for index, signal in enumerate(filtered_reference, start=1):
        key = _signal_lookup_key(signal)
        render_tier_signal_card_simple(
          signal=signal,
          display_signal=display_signal_lookup.get(key, {}),
          search_run_id=run_id,
          key_namespace="simple_reference_low",
          index=index,
        )

  if should_show_full_signal_details() and not initial_baseline:
    st.multiselect(
      "変化",
      ["New", "Rising", "Dropped", "Stable"],
      default=[],
      key="ui_simple_status_filter",
      placeholder="すべて表示",
    )

  return {"save_snapshot": False}


__all__ = [
  "filter_signals_for_simple_display",
  "render_simple_signals_tab",
  "split_top_and_remaining",
]
