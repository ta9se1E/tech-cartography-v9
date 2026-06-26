"""v8 patent shortlist tab skeleton (Phase 27B)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from tech_cartography.services.v8_sources_table import filter_patent_sources, load_source_candidates
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_next_action_box
from tech_cartography.ui.v8_input_ui import get_v8_input_state
from tech_cartography.ui.v8_tab_config import STATE_V8_SELECTED_CASE, V8_TAB_LABELS


def _draft_patent_rows(patent_rows: list[dict[str, str]], *, limit: int = 5) -> list[dict[str, str]]:
  draft: list[dict[str, str]] = []
  for index, row in enumerate(patent_rows[:limit], start=1):
    draft.append(
      {
        "rank": str(index),
        "publication_number": row.get("publication_number", ""),
        "title": row.get("title", ""),
        "organization": row.get("organization", ""),
        "year": row.get("year", ""),
        "url": row.get("url", ""),
        "why_read": "【draft placeholder】請求項・実施例の優先確認理由は Phase27D でスコアリング",
        "technical_axis": "【draft placeholder】case_profile の expected_claim_axes を参照",
        "evidence_needed": "【draft placeholder】一次公報・論文の確認要否",
        "next_action": "【draft placeholder】原典 URL で請求項を人手確認",
        "display_status": "draft",
      },
    )
  return draft


def render_v8_patent_shortlist_tab(*, project_root: Path | str) -> None:
  root = Path(project_root)
  state = get_v8_input_state()
  case_id = str(state.get("selected_case_id") or st.session_state.get(STATE_V8_SELECTED_CASE) or "").strip()

  st.markdown("### 読むべき特許 Top 5（draft）")
  st.markdown(
    render_caution_box(
      "このタブは <strong>Phase27B 骨格</strong> です。"
      " 表示は source_candidates.csv からの仮候補であり、本格スコアリングは Phase27D で実装します。"
      " 架空の根拠やスコアは表示しません。"
    ),
    unsafe_allow_html=True,
  )

  all_rows = load_source_candidates(case_id or None, project_root=root)
  patent_rows = filter_patent_sources(all_rows)
  if not patent_rows:
    st.info("特許 type の Sources がありません。入力タブで案件を選んでください。")
    return

  draft_rows = _draft_patent_rows(patent_rows, limit=5)
  df = pd.DataFrame(draft_rows)
  st.dataframe(df, use_container_width=True, hide_index=True)

  st.markdown(render_info_box("各行は draft / placeholder です。確定ランキングではありません。"), unsafe_allow_html=True)

  st.markdown(
    render_next_action_box(f"次は「{V8_TAB_LABELS['claim_map']}」で請求項の技術軸整理を確認してください。"),
    unsafe_allow_html=True,
  )
