"""v8 input tab (Phase 27B / 27R.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.services.v8_large_candidate_import import import_large_candidates
from tech_cartography.services.v8_sources_table import load_case_profile
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_next_action_box
from tech_cartography.ui.v8_bigquery_admin_ui import render_bigquery_admin_section
from tech_cartography.services.v8_google_patents_links import save_patent_pdf_upload
from tech_cartography.services.v8_large_candidate_shortlist import load_top5_publications
from tech_cartography.ui.v8_google_patents_links_ui import load_and_render_top5_pdf_links
from tech_cartography.ui.v8_judge_mode_copy import PDF_UPLOAD_HELP
from tech_cartography.ui.v8_patent_pdf_text_extract_ui import render_top5_pdf_text_extract_section
from tech_cartography.ui.v8_judge_mode_ui import render_judge_conclusion_card, render_judge_next_tab_hint
from tech_cartography.ui.v8_research_theme_ui import render_research_theme_section
from tech_cartography.ui.v8_tab_config import STATE_V8_INPUT, STATE_V8_SELECTED_CASE, V8_CASE_SAMPLES, V8_TAB_LABELS
from tech_cartography.ui.v8_demo_flow_ui import render_demo_flow_banner

LC_IMPORT_MAX_ROWS = 1000


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

  render_judge_conclusion_card("input")
  render_judge_next_tab_hint("input")

  st.markdown("### 入力・テーマ設定")

  with st.expander("詳細ガイド", expanded=False):
    st.markdown(
      render_info_box(
        "<strong>研究テーマと候補データの起点</strong> — Case を選び、"
        "テーマ・キーワードを設定して CSV/Excel を取り込みます。"
      ),
      unsafe_allow_html=True,
    )
    render_demo_flow_banner(
      project_root=root,
      current_tab="input",
      tab_purpose="テーマ設定と候補データ取込",
      next_tab_key="sources",
    )

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

  theme_case = selected if selected != "（案件を選ばない）" else V8_CASE_SAMPLES[0]["case_id"]
  render_research_theme_section(case_id=theme_case, project_root=root, show_advanced=True)

  with st.expander("CSV/Excelを取り込む", expanded=False):
    st.markdown(
      render_caution_box(
        "CSV/Excel の実データのみ使用します。"
        " <strong>1000件は母集団</strong>であり、全件を Claim Map / Evidence Map で深掘りしません。"
      ),
      unsafe_allow_html=True,
    )
    lc_case = st.selectbox(
      "案件",
      options=[s["case_id"] for s in V8_CASE_SAMPLES],
      key="v8_large_import_case",
    )
    lc_source_type = st.selectbox(
      "source_type default",
      options=["patent", "paper", "web", "company"],
      key="v8_large_source_type",
    )
    lc_file = st.file_uploader(
      "CSV / Excel (csv, xlsx)",
      type=["csv", "xlsx"],
      key="v8_large_candidate_upload",
    )
    if st.button("Import Large Candidate File", key="v8_large_import_btn", type="primary"):
      if lc_file is None:
        st.warning("ファイルを選択してください。")
      elif not lc_case:
        st.warning("案件を選択してください。")
      else:
        tmp_dir = root / "outputs" / "tmp_large_import"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(lc_file.name).suffix or ".csv"
        tmp_path = tmp_dir / f"{lc_case}_upload{suffix}"
        tmp_path.write_bytes(lc_file.getvalue())
        result = import_large_candidates(
          case_id=lc_case,
          input_path=tmp_path,
          max_rows=LC_IMPORT_MAX_ROWS,
          default_source_type=lc_source_type,
          project_root=root,
        )
        st.session_state["v8_last_large_import"] = result.to_dict()
        st.success(
          f"import完了 — accepted={result.accepted_row_count} / rejected={result.rejected_row_count}"
        )
    last_import = st.session_state.get("v8_last_large_import")
    if isinstance(last_import, dict):
      st.caption(f"input_row_count: {last_import.get('input_row_count')}")
      st.caption(f"accepted_row_count: {last_import.get('accepted_row_count')}")

  st.markdown("#### PDFアップロード")
  st.caption(PDF_UPLOAD_HELP)
  st.caption(
    "Google PatentsのページからユーザーがPDFを確認・取得してください。"
  )
  load_and_render_top5_pdf_links(theme_case, root, key_prefix="v8_gp_input")

  top5_pubs = load_top5_publications(theme_case, root)
  pub_options = top5_pubs if top5_pubs else ["（Top5未生成）"]
  pdf_pub = st.selectbox(
    "PDF対象特許（Top5）",
    options=pub_options,
    key="v8_input_pdf_pub",
  )
  pdf_file = st.file_uploader("特許PDF（公報PDF）", type=["pdf"], key="v8_input_pdf_upload")
  if pdf_file is not None and pdf_pub and not pdf_pub.startswith("（"):
    if st.button("PDFを保存", key="v8_input_pdf_save", type="primary"):
      save_patent_pdf_upload(
        case_id=theme_case,
        publication_number=pdf_pub,
        pdf_bytes=pdf_file.getvalue(),
        original_filename=pdf_file.name,
        project_root=root,
      )
      uploads = st.session_state.get("v8_patent_pdf_uploads")
      if not isinstance(uploads, dict):
        uploads = {}
      uploads[pdf_pub] = pdf_file.name
      st.session_state["v8_patent_pdf_uploads"] = uploads
      state["pdf_upload_note"] = f"saved: {pdf_pub} ← {pdf_file.name}"
      st.success(state["pdf_upload_note"])
  elif pdf_file is not None:
    state["pdf_upload_note"] = f"selected: {pdf_file.name} — 特許を選んで「PDFを保存」を押してください"
    st.caption(state["pdf_upload_note"])

  render_top5_pdf_text_extract_section(theme_case, root, key_prefix="v8_input_pdf_text")

  with st.expander("詳細設定（BigQuery SQL生成・管理者向け）", expanded=False):
    render_bigquery_admin_section(case_id=theme_case, project_root=root)

  st.session_state[STATE_V8_INPUT] = state

  st.markdown(
    render_next_action_box(
      f"次: 「{V8_TAB_LABELS['sources']}」で候補母集団の件数と出自を確認してください。"
    ),
    unsafe_allow_html=True,
  )
