"""Simple Mode signal card helpers."""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from services_v9.simple_tier_display import tier_display_label_ja
from services_v9.study_demo_ui_mode import should_show_technical_ids
from ui_v9.labels import type_label_ja
from ui_v9.study_demo_source_link import render_external_source_link


def render_tier_signal_card_simple(
  *,
  signal: Any,
  display_signal: Mapping[str, Any] | None = None,
  search_run_id: str = "",
  key_namespace: str,
  index: int,
) -> None:
  title = str(getattr(signal, "title", "") or (display_signal or {}).get("title", "") or "").strip()
  if not title:
    return
  tier = str(
    (display_signal or {}).get("relevance_tier", "")
    or (display_signal or {}).get("study_demo", {}).get("relevance_tier", "")
    or getattr(signal, "tier", "")
    or "D"
  )
  tier_label = tier_display_label_ja(tier)
  st.markdown(f"**{title}**")
  st.caption(f"{type_label_ja(signal.type)} | {tier_label}")
  summary = str(getattr(signal, "summary", "") or (display_signal or {}).get("summary", "") or "").strip()
  if summary:
    st.write(summary[:240])
  render_external_source_link(
    signal,
    key_namespace=key_namespace,
    search_run_id=search_run_id,
    label="原典を確認",
  )
  if should_show_technical_ids():
    with st.expander("技術情報（シグナル）", expanded=False):
      st.write(f"- tier: `{tier}`")
      st.write(f"- signal_id: `{(display_signal or {}).get('id', '')}`")


__all__ = ["render_tier_signal_card_simple"]
