"""v8 Claim Map tab skeleton (Phase 27B)."""

from __future__ import annotations

import streamlit as st

from tech_cartography.ui.easy_japanese_ui import render_info_box, render_next_action_box
from tech_cartography.ui.v8_tab_config import (
  CLAIM_MAP_PLANNED_COLUMNS,
  CLAIM_MAP_TECHNICAL_AXES,
  V8_TAB_LABELS,
)


def render_v8_claim_map_tab() -> None:
  st.markdown("### Claim Map（Phase27E 本実装予定）")
  st.caption("入力特許から claim を取り出し、技術軸へ分類する画面の入口です。")

  st.markdown("#### 炭素繊維向け技術軸")
  for axis in CLAIM_MAP_TECHNICAL_AXES:
    st.markdown(f"- `{axis}`")

  st.markdown("#### 予定列")
  cols = pd_columns_markdown(CLAIM_MAP_PLANNED_COLUMNS)
  st.markdown(cols)

  st.markdown(
    render_info_box(
      "Phase27E で patent_id / claim_no 単位の Claim Map v1 を実装します。"
      " 現時点では抽出・分類は行いません。"
    ),
    unsafe_allow_html=True,
  )

  st.markdown(
    render_next_action_box(f"次は「{V8_TAB_LABELS['evidence_map']}」で Evidence 対応付けの予定構造を確認してください。"),
    unsafe_allow_html=True,
  )


def pd_columns_markdown(columns: tuple[str, ...]) -> str:
  return "\n".join(f"- `{col}`" for col in columns)
