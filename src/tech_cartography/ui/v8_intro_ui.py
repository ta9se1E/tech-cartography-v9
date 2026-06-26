"""v8 intro tab (Phase 27B)."""

from __future__ import annotations

import streamlit as st

from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box
from tech_cartography.ui.v8_text_rendering import render_next_action_card
from tech_cartography.ui.v8_tab_config import V8_STATUS_CAPTION, V8_TAB_LABELS


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

  st.markdown("#### Phase27L — 推奨デモ操作手順")
  demo_steps = [
    "入力タブで 1000件候補 CSV を取り込む",
    "Sources一覧で母集団を見る",
    "読むべき特許で Top100 → Top20 → Top5 を見る",
    "Claim Map で Top5 の claim 本文状態を見る",
    "必要なら claim 本文を手動投入する",
    "Evidence Map で supporting evidence candidate を見る",
    "Gap / Next Actions で未確認事項と次アクションを見る",
    "定点観測で次回タスクと Digest 計画を見る",
    "Export で Demo Polish Pack を出す",
  ]
  for index, step in enumerate(demo_steps, start=1):
    st.markdown(f"{index}. {step}")
  st.markdown(
    render_info_box(
      "Evidence Map is not proof — paper / web / company は candidate です。"
      " Gap is not invalidity / weakness — 未確認事項です。"
      " claim 本文はユーザー提供のみ（自動生成しません）。"
    ),
    unsafe_allow_html=True,
  )

  st.markdown("#### Phase27K — Manual Claim Injection")
  st.markdown(
    render_info_box(
      "<strong>claim 本文はユーザーが一次情報からコピーしたもののみ</strong>を投入します。"
      " システムは claim 本文を生成しません。"
      " Claim Map タブで手動投入 → Evidence Map / Gap / 定点観測を再生成し、"
      " Evidence Map の見え方を改善します（paper/web/company は引き続き candidate）。"
    ),
    unsafe_allow_html=True,
  )

  st.markdown("#### Phase27I — 3案件ローカル検証")
  st.markdown(
    render_info_box(
      "Cloud 反映前に、Export タブで<strong>3案件検証パック</strong>を作成し、"
      " Sources → Top特許 → Claim Map → Evidence Map → Gap / Next Actions → 定点観測 → Export "
      "の一連の流れがローカルで成立するか確認します。"
      " claim 本文未取得は needs_claim_text として正しく warning 扱いです。"
    ),
    unsafe_allow_html=True,
  )

  st.markdown("#### 現在の開発状態")
  st.caption(V8_STATUS_CAPTION)

  st.markdown(
    render_next_action_card(
      "次にやること",
      f"「{V8_TAB_LABELS['evidence_map']}」→「{V8_TAB_LABELS['gap_next_actions']}」→"
      f"「{V8_TAB_LABELS['export']}」の順でデモ操作を確認してください。",
    ),
    unsafe_allow_html=True,
  )
