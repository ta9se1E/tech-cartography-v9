"""v8 input tab (Phase 27B)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.services.v8_large_candidate_import import import_large_candidates
from tech_cartography.services.v8_sources_table import load_case_profile
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_next_action_box
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

  st.markdown("#### 1000件候補CSV/Excelを取り込む (Phase27J.0)")
  st.markdown(
    render_caution_box(
      "この Phase では外部 API / BigQuery 実行 / Web 検索を行いません。"
      " CSV/Excel の実データのみ使用します。fake URL / fake DOI は作りません。"
      " <strong>1000件は母集団</strong>であり、全件を Claim Map / Evidence Map で深掘りしません。"
    ),
    unsafe_allow_html=True,
  )
  lc_case = st.selectbox(
    "Large Candidate 案件",
    options=[s["case_id"] for s in V8_CASE_SAMPLES],
    key="v8_large_import_case",
  )
  lc_max_rows = st.number_input("max_rows", min_value=1, max_value=1000, value=1000, key="v8_large_max_rows")
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
        max_rows=int(lc_max_rows),
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
    st.caption(f"output: {last_import.get('output_candidates_path')}")

  st.markdown("#### ファイルアップロード（小規模 demo sources）")
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
