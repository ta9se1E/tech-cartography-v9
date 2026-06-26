"""v8 input tab (Phase 27B)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.services.v8_sources_table import load_case_profile
from tech_cartography.ui.easy_japanese_ui import render_info_box, render_next_action_box
from tech_cartography.ui.v8_tab_config import STATE_V8_INPUT, STATE_V8_SELECTED_CASE, V8_CASE_SAMPLES, V8_TAB_LABELS


def default_v8_input_state() -> dict[str, Any]:
  return {
    "research_theme": "",
    "keywords": "",
    "focus_companies": "",
    "patent_numbers": "",
    "google_patents_urls": "",
    "selected_case_id": "",
    "csv_upload_note": "",
    "pdf_upload_note": "",
  }


def get_v8_input_state() -> dict[str, Any]:
  state = st.session_state.get(STATE_V8_INPUT)
  if not isinstance(state, dict):
    state = default_v8_input_state()
    st.session_state[STATE_V8_INPUT] = state
  return state


def render_v8_input_tab(*, project_root: Path | str) -> None:
  root = Path(project_root)
  state = get_v8_input_state()

  st.markdown("### 研究テーマと入力")
  st.caption("このタブでは外部API・BigQuery・メール送信・Scheduler は実行しません。")

  case_options = ["（案件を選ばない）"] + [sample["case_id"] for sample in V8_CASE_SAMPLES]
  case_labels = {sample["case_id"]: sample["label"] for sample in V8_CASE_SAMPLES}
  current_case = str(state.get("selected_case_id") or st.session_state.get(STATE_V8_SELECTED_CASE) or "")
  if current_case and current_case in case_options:
    default_index = case_options.index(current_case)
  else:
    default_index = 0

  selected = st.selectbox(
    "3案件サンプル",
    options=case_options,
    index=default_index,
    format_func=lambda cid: case_labels.get(cid, cid) if cid != "（案件を選ばない）" else cid,
    key="v8_input_case_select",
  )
  if selected == "（案件を選ばない）":
    state["selected_case_id"] = ""
    st.session_state[STATE_V8_SELECTED_CASE] = ""
  else:
    state["selected_case_id"] = selected
    st.session_state[STATE_V8_SELECTED_CASE] = selected
    profile = load_case_profile(selected, root)
    if profile:
      st.markdown(render_info_box(f"テーマ: {profile.get('theme', '')}"), unsafe_allow_html=True)

  state["research_theme"] = st.text_area(
    "研究テーマ",
    value=str(state.get("research_theme") or ""),
    key="v8_input_research_theme",
  )
  state["keywords"] = st.text_area(
    "キーワード（カンマ区切り）",
    value=str(state.get("keywords") or ""),
    key="v8_input_keywords",
  )
  state["focus_companies"] = st.text_input(
    "注目企業",
    value=str(state.get("focus_companies") or ""),
    key="v8_input_companies",
  )
  state["patent_numbers"] = st.text_area(
    "特許番号リスト（1行1件）",
    value=str(state.get("patent_numbers") or ""),
    key="v8_input_patents",
  )
  state["google_patents_urls"] = st.text_area(
    "Google Patents URL（1行1件）",
    value=str(state.get("google_patents_urls") or ""),
    key="v8_input_gp_urls",
  )

  st.markdown("#### ファイルアップロード（導線のみ）")
  csv_file = st.file_uploader("CSV / Excel 相当（CSV）", type=["csv"], key="v8_input_csv_upload")
  if csv_file is not None:
    state["csv_upload_note"] = f"uploaded: {csv_file.name} ({csv_file.size} bytes) — draft保存のみ"
    st.caption(state["csv_upload_note"])
  pdf_file = st.file_uploader("PDF（手動全文確認用）", type=["pdf"], key="v8_input_pdf_upload")
  if pdf_file is not None:
    state["pdf_upload_note"] = f"uploaded: {pdf_file.name} ({pdf_file.size} bytes) — draft保存のみ"
    st.caption(state["pdf_upload_note"])

  st.session_state[STATE_V8_INPUT] = state

  st.markdown("#### 入力サマリー")
  summary_rows = [
    ("研究テーマ", state.get("research_theme") or "（未入力）"),
    ("キーワード", state.get("keywords") or "（未入力）"),
    ("注目企業", state.get("focus_companies") or "（未入力）"),
    ("特許番号", state.get("patent_numbers") or "（未入力）"),
    ("選択案件", state.get("selected_case_id") or "（未選択）"),
  ]
  for label, value in summary_rows:
    st.markdown(f"- **{label}**: {value}")

  st.markdown(
    render_next_action_box(
      f"流れ: 「{V8_TAB_LABELS['sources']}」→「{V8_TAB_LABELS['patent_shortlist']}」→「{V8_TAB_LABELS['claim_map']}」。"
      f" 案件選択後、Sources で patent を確認し、読むべき特許 Top N（heuristic）を生成してください。"
    ),
    unsafe_allow_html=True,
  )
