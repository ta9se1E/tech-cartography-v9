"""v8 intro tab (Phase 27B / 27R.2)."""

from __future__ import annotations

import streamlit as st

from tech_cartography.ui.easy_japanese_ui import render_info_box
from tech_cartography.ui.v8_judge_mode_copy import INTRO_SAFETY_NOTICES, INTRO_FUNNEL_SUMMARY, INTRO_SERVICE_SUMMARY
from tech_cartography.ui.v8_judge_mode_ui import (
  render_judge_conclusion_card,
  render_judge_next_tab_hint,
  render_judge_three_minute_guide,
)


def render_v8_intro_tab() -> None:
  st.markdown("### はじめに｜Judge Overview")
  render_judge_conclusion_card("intro")

  st.markdown(
    render_info_box(f"<strong>{INTRO_SERVICE_SUMMARY}</strong>"),
    unsafe_allow_html=True,
  )

  render_judge_three_minute_guide(expanded=True)

  st.markdown("#### 成果ファネル（Case 1）")
  st.markdown(INTRO_FUNNEL_SUMMARY)

  st.markdown("#### 読み方")
  for notice in INTRO_SAFETY_NOTICES:
    st.markdown(f"- {notice}")

  render_judge_next_tab_hint("intro")
