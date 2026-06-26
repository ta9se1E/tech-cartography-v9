"""v8 Export tab skeleton (Phase 27B)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from tech_cartography.runtime.live_artifact_paths import describe_live_artifact_storage
from tech_cartography.services.live_evidence_gap_builder import find_latest_evidence_gap_path
from tech_cartography.services.live_strategic_watch_brief import find_latest_strategic_watch_brief_path
from tech_cartography.services.live_weekly_decision_cockpit import find_latest_weekly_decision_cockpit_path
from tech_cartography.services.v8_sources_table import filter_patent_sources, load_source_candidates, sources_to_csv_text
from tech_cartography.ui.easy_japanese_ui import render_info_box
from tech_cartography.ui.v8_input_ui import get_v8_input_state
from tech_cartography.ui.v8_tab_config import STATE_V8_SELECTED_CASE


def _artifact_link(path: Path | None) -> None:
  if path and path.exists():
    st.caption(str(path))
  else:
    st.caption("（未生成）")


def render_v8_export_tab(*, project_root: Path | str) -> None:
  root = Path(project_root)
  state = get_v8_input_state()
  case_id = str(state.get("selected_case_id") or st.session_state.get(STATE_V8_SELECTED_CASE) or "").strip()

  st.markdown("### Export")
  st.caption("Phase27C 以降で本格 Export package を実装します。既存 artifact があればパスを表示します。")

  rows = load_source_candidates(case_id or None, project_root=root)
  if rows:
    st.download_button(
      "Sources一覧 CSV",
      data=sources_to_csv_text(rows).encode("utf-8"),
      file_name="sources_index.csv",
      mime="text/csv",
      key="v8_export_sources_csv",
    )
  else:
    st.caption("Sources一覧 CSV — データなし")

  patent_rows = filter_patent_sources(rows)
  if patent_rows:
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(
      buffer,
      fieldnames=["publication_number", "title", "organization", "year", "url", "display_status"],
    )
    writer.writeheader()
    for row in patent_rows[:5]:
      writer.writerow(
        {
          "publication_number": row.get("publication_number", ""),
          "title": row.get("title", ""),
          "organization": row.get("organization", ""),
          "year": row.get("year", ""),
          "url": row.get("url", ""),
          "display_status": "draft",
        },
      )
    st.download_button(
      "読むべき特許 CSV（draft）",
      data=buffer.getvalue().encode("utf-8"),
      file_name="top_patents_draft.csv",
      mime="text/csv",
      key="v8_export_patents_csv",
    )

  st.markdown("#### プレースホルダ / 既存 artifact")
  st.markdown("- Claim Map CSV — Phase27E")
  st.markdown("- Evidence Map CSV — Phase27F")

  st.markdown("**Evidence Gap**")
  _artifact_link(find_latest_evidence_gap_path(root))

  st.markdown("**Strategic Watch Brief**")
  brief_path = find_latest_strategic_watch_brief_path(root)
  _artifact_link(brief_path)
  if brief_path and brief_path.exists():
    md_path = brief_path.with_suffix(".md")
    if md_path.exists():
      st.download_button(
        "Strategic Watch Brief Markdown",
        data=md_path.read_bytes(),
        file_name=md_path.name,
        mime="text/markdown",
        key="v8_export_brief_md",
      )

  st.markdown("**Weekly Decision Cockpit**")
  cockpit_path = find_latest_weekly_decision_cockpit_path(root)
  _artifact_link(cockpit_path)

  st.markdown("#### Export package（予定）")
  st.markdown(render_info_box("Phase27C で case 単位 ZIP bundle を実装予定です。"), unsafe_allow_html=True)

  storage = describe_live_artifact_storage(root)
  st.caption(f"artifact root: {storage.get('outputs_root', '')}")
