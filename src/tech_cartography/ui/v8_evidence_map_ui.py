"""v8 Evidence Map tab (Phase 27F preview + Phase 27E linkage)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from tech_cartography.services.v8_claim_map_export import find_latest_claim_map_dir
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_next_action_box
from tech_cartography.ui.v8_claim_map_ui import pd_columns_markdown
from tech_cartography.ui.v8_input_ui import get_v8_input_state
from tech_cartography.ui.v8_tab_config import (
  EVIDENCE_MAP_PLANNED_COLUMNS,
  EVIDENCE_SUPPORT_LEVELS,
  STATE_V8_SELECTED_CASE,
  V8_CASE_SAMPLES,
  V8_TAB_LABELS,
)


def render_v8_evidence_map_tab(*, project_root: Path | str) -> None:
  root = Path(project_root)
  state = get_v8_input_state()
  default_case = str(state.get("selected_case_id") or st.session_state.get(STATE_V8_SELECTED_CASE) or "").strip()
  case_ids = [s["case_id"] for s in V8_CASE_SAMPLES]
  labels = {s["case_id"]: s["label"] for s in V8_CASE_SAMPLES}
  default_idx = case_ids.index(default_case) if default_case in case_ids else 0

  st.markdown("### Evidence Map（Phase27F 本実装予定）")
  st.markdown(
    render_caution_box(
      "claim / example / paper / web の対応付け画面です。"
      " Web Signal は候補情報（candidate_information_only）。"
      " FTO・侵害・有効性判断ではありません。"
    ),
    unsafe_allow_html=True,
  )

  selected_case = st.selectbox(
    "案件",
    options=case_ids,
    index=default_idx,
    format_func=lambda cid: labels[cid],
    key="v8_evidence_map_case",
  )

  claim_map_dir = find_latest_claim_map_dir(selected_case, root)
  if claim_map_dir and claim_map_dir.exists():
    st.caption(f"最新 Claim Map artifact: {claim_map_dir}")
    manifest = claim_map_dir / "claim_map_manifest.json"
    if manifest.exists():
      st.caption(f"manifest: {manifest}")
  else:
    st.caption("Claim Map は未生成 — 「Claim Map」タブで Generate してください。")

  st.markdown(
    render_info_box(
      "Phase27F で Claim Map の technical_axis_labels / evidence_needed を入力に、"
      "実施例・論文・Web Signal との対応付けを本格実装します。"
      " 現時点では対応付けロジックは実行しません。"
    ),
    unsafe_allow_html=True,
  )

  st.markdown("#### 予定列")
  st.markdown(pd_columns_markdown(EVIDENCE_MAP_PLANNED_COLUMNS))

  st.markdown("#### support_level 候補")
  for level in EVIDENCE_SUPPORT_LEVELS:
    st.markdown(f"- `{level}`")

  st.markdown(
    render_next_action_box(f"次は「{V8_TAB_LABELS['gap_next_actions']}」で Gap と次の確認事項を見てください。"),
    unsafe_allow_html=True,
  )
