"""v8 intro tab (Phase 27B)."""

from __future__ import annotations

import streamlit as st

from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_next_action_box
from tech_cartography.ui.v8_tab_config import V8_TAB_LABELS


def render_v8_intro_tab() -> None:
  st.markdown("### Tech Cartography v8")
  st.markdown(
    render_info_box(
      "特許の請求項・実施例・論文・Web情報を対応付け、"
      "<strong>読むべき特許</strong>・<strong>Claim / Evidence / Gap</strong>・"
      "<strong>次に確認すべき一次情報</strong>を整理し、定点観測ループへ反映する R&D Intelligence Agent です。"
    ),
    unsafe_allow_html=True,
  )

  st.markdown("#### 対象ユーザー")
  for item in (
    "日本の研究者",
    "中小製造業の技術者",
    "知財専任者がいない R&D チーム",
  ):
    st.markdown(f"- {item}")

  st.markdown("#### このサービスでできること")
  for item in (
    "関連特許を整理する",
    "Sources一覧を作る",
    "読むべき特許を絞る",
    "Claim Map を作る",
    "Evidence Map を作る",
    "Evidence Gap を出す",
    "Next Verification Actions を出す",
    "定点観測へ反映する",
  ):
    st.markdown(f"- {item}")

  st.markdown("#### このサービスでできないこと")
  st.markdown(
    render_caution_box(
      "FTO判断・侵害判断・有効性判断・法的結論・確定事実の断定は行いません。"
      " Web Signal は候補情報（candidate_information_only）として扱います。"
    ),
    unsafe_allow_html=True,
  )

  st.markdown("#### 全体フロー")
  flow = [
    V8_TAB_LABELS["input"],
    V8_TAB_LABELS["sources"],
    V8_TAB_LABELS["patent_shortlist"],
    V8_TAB_LABELS["claim_map"],
    V8_TAB_LABELS["evidence_map"],
    V8_TAB_LABELS["gap_next_actions"],
    V8_TAB_LABELS["fixed_point_observation"],
    V8_TAB_LABELS["export"],
  ]
  for index, step in enumerate(flow, start=1):
    st.markdown(f"{index}. {step}")

  st.markdown("#### 現在の開発状態")
  st.caption("v8 local-first — 3案件検証中（UI骨格 Phase27B、本格分析は Phase27C 以降）")

  st.markdown(
    render_next_action_box(f"次は「{V8_TAB_LABELS['input']}」タブでテーマと案件を選んでください。"),
    unsafe_allow_html=True,
  )
