"""v8 Evidence Map tab skeleton (Phase 27B)."""

from __future__ import annotations

import streamlit as st

from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_next_action_box
from tech_cartography.ui.v8_claim_map_ui import pd_columns_markdown
from tech_cartography.ui.v8_tab_config import (
  EVIDENCE_MAP_PLANNED_COLUMNS,
  EVIDENCE_SUPPORT_LEVELS,
  V8_TAB_LABELS,
)


def render_v8_evidence_map_tab() -> None:
  st.markdown("### Evidence Map（Phase27F 本実装予定）")
  st.markdown(
    render_caution_box(
      "claim / example / paper / web の対応付け画面です。"
      " Web Signal は候補情報（candidate_information_only）。"
      " FTO・侵害・有効性判断ではありません。"
    ),
    unsafe_allow_html=True,
  )

  st.markdown("#### 予定列")
  st.markdown(pd_columns_markdown(EVIDENCE_MAP_PLANNED_COLUMNS))

  st.markdown("#### support_level 候補")
  for level in EVIDENCE_SUPPORT_LEVELS:
    st.markdown(f"- `{level}`")

  st.markdown(
    render_info_box("Phase27F で Claim-Evidence 対応の本格マップを実装します。現時点では対応付けは行いません。"),
    unsafe_allow_html=True,
  )

  st.markdown(
    render_next_action_box(f"次は「{V8_TAB_LABELS['gap_next_actions']}」で Gap と次の確認事項を見てください。"),
    unsafe_allow_html=True,
  )
