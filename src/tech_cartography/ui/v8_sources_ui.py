"""v8 Sources tab skeleton (Phase 27B)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from tech_cartography.services.v8_sources_table import (
  SOURCE_CSV_COLUMNS,
  load_source_candidates,
  sources_to_csv_text,
)
from tech_cartography.ui.easy_japanese_ui import render_info_box, render_next_action_box, render_warning_box
from tech_cartography.ui.v8_input_ui import get_v8_input_state
from tech_cartography.ui.v8_tab_config import STATE_V8_SELECTED_CASE, V8_TAB_LABELS


def render_v8_sources_tab(*, project_root: Path | str) -> None:
  root = Path(project_root)
  state = get_v8_input_state()
  case_id = str(state.get("selected_case_id") or st.session_state.get(STATE_V8_SELECTED_CASE) or "").strip()

  st.markdown("### Sources一覧")
  st.caption(
    "特許・論文・Web情報を同じ表で確認します。"
    " Web Signal 行は候補情報（candidate_information_only）であり確定事実ではありません。"
  )

  rows = load_source_candidates(case_id or None, project_root=root)
  if not rows:
    st.markdown(render_warning_box("まだ Sources がありません。入力タブで案件を選ぶか、Phase27C で統合生成します。"), unsafe_allow_html=True)
    return

  if case_id:
    st.caption(f"表示案件: {case_id}")
  else:
    st.caption("全案件の source_candidates.csv を表示しています。")

  df = pd.DataFrame(rows, columns=list(SOURCE_CSV_COLUMNS))
  st.dataframe(df, width="stretch", hide_index=True)

  web_rows = [r for r in rows if "web" in str(r.get("type") or "").lower()]
  if web_rows:
    st.markdown(
      render_info_box(
        f"Web Signal {len(web_rows)} 件 — candidate_information_only。"
        " Claim の根拠として断定しません。"
      ),
      unsafe_allow_html=True,
    )

  st.download_button(
    "Sources一覧 CSV をダウンロード",
    data=sources_to_csv_text(rows).encode("utf-8"),
    file_name="sources_index.csv",
    mime="text/csv",
    key="v8_sources_csv_download",
  )

  st.markdown(
    render_next_action_box(f"次は「{V8_TAB_LABELS['patent_shortlist']}」で読むべき特許を確認してください。"),
    unsafe_allow_html=True,
  )
