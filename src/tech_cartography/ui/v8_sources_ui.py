"""v8 unified Sources tab (Phase 27C)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from tech_cartography.runtime.v8_sources_schema import SAFETY_EXPORT_NOTICES
from tech_cartography.services.v8_export_package import build_export_package, records_to_csv_text, records_to_markdown
from tech_cartography.services.v8_large_candidate_import import (
  large_candidates_paths,
  load_large_candidates_csv,
)
from tech_cartography.services.v8_sources_repository import filter_sources_table, load_sources_table, resolve_case_name
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_next_action_box, render_warning_box
from tech_cartography.ui.v8_input_ui import get_v8_input_state
from tech_cartography.ui.v8_tab_config import STATE_V8_SELECTED_CASE, V8_CASE_SAMPLES, V8_TAB_LABELS

DISPLAY_COLUMNS = [
  "source_id",
  "case_id",
  "source_type",
  "title",
  "organization",
  "year",
  "publication_number",
  "url",
  "source_status",
  "evidence_role",
  "reliability_label",
  "verification_status",
  "candidate_information_only",
  "human_review_required",
]


def _case_filter_options() -> list[tuple[str, str]]:
  options: list[tuple[str, str]] = [("all", "All cases")]
  for sample in V8_CASE_SAMPLES:
    options.append((sample["case_id"], sample["label"]))
  return options


def _render_large_candidate_sources(*, root: Path, default_case: str) -> None:
  case_options = _case_filter_options()
  case_ids = [cid for cid, _ in case_options if cid != "all"]
  case_labels = {cid: label for cid, label in case_options}
  default_idx = case_ids.index(default_case) if default_case in case_ids else 0
  selected_case = st.selectbox(
    "案件",
    options=case_ids,
    index=default_idx,
    format_func=lambda cid: case_labels[cid],
    key="v8_large_sources_case",
  )
  paths = large_candidates_paths(selected_case, root)
  records = load_large_candidates_csv(paths["population"])
  if not records and paths["deduped"].exists():
    records = load_large_candidates_csv(paths["deduped"])
  if not records:
    st.warning("source_candidates_large.csv がありません。入力タブで Large Candidate を取り込んでください。")
    return

  stype = st.selectbox("source_type", ["all", "patent", "paper", "web", "company"], key="v8_large_stype")
  stage = st.selectbox(
    "stage_label",
    ["all", "population", "deduped", "scored", "top100", "top20", "top5"],
    key="v8_large_stage",
  )
  keyword = st.text_input("keyword", key="v8_large_kw")
  hr_only = st.checkbox("human_review_required only", key="v8_large_hr")

  filtered = records
  if stype != "all":
    filtered = [r for r in filtered if r.source_type == stype]
  if stage != "all":
    filtered = [r for r in filtered if r.stage_label == stage]
  if keyword.strip():
    kw = keyword.lower()
    filtered = [r for r in filtered if kw in _search_blob_lc(r)]
  if hr_only:
    filtered = [r for r in filtered if r.human_review_required]

  dup_count = sum(1 for r in records if r.is_duplicate)
  m1, m2, m3, m4 = st.columns(4)
  m1.metric("total_candidates", len(records))
  m2.metric("displayed", len(filtered))
  m3.metric("duplicate_count", dup_count)
  m4.metric("missing_title", sum(1 for r in records if not r.title))

  display_cols = [
    "publication_number", "title", "organization", "year", "source_type",
    "heuristic_score", "stage_label", "keyword_match_count", "human_review_required",
  ]
  preview = filtered[:100]
  rows = [{c: getattr(r, c, "") for c in display_cols} for r in preview]
  st.dataframe(pd.DataFrame(rows, columns=display_cols), width="stretch", hide_index=True)
  if len(filtered) > 100:
    st.caption(f"先頭100件のみ表示（全 {len(filtered)} 件）")

  for label, path in (
    ("source_candidates_large.csv", paths["population"]),
    ("source_candidates_large_deduped.csv", paths["deduped"]),
    ("quality report", paths["quality_report"]),
  ):
    if path.exists():
      st.download_button(
        f"Download {label}",
        data=path.read_bytes(),
        file_name=path.name,
        mime="text/csv" if path.suffix == ".csv" else "text/markdown",
        key=f"v8_large_dl_{path.name}",
      )

  st.markdown(
    render_next_action_box(
      f"次は「{V8_TAB_LABELS['patent_shortlist']}」で Large Candidate mode の Top100/Top20/Top5 を生成してください。"
    ),
    unsafe_allow_html=True,
  )


def _search_blob_lc(rec) -> str:
  return f"{rec.title} {rec.organization} {rec.publication_number} {rec.abstract}".lower()


def render_v8_sources_tab(*, project_root: Path | str) -> None:
  root = Path(project_root)
  state = get_v8_input_state()
  default_case = str(state.get("selected_case_id") or st.session_state.get(STATE_V8_SELECTED_CASE) or "").strip()

  st.markdown("### Sources一覧")
  st.markdown(
    render_caution_box(
      "FTO、侵害、有効性判断、法的結論は行いません。"
      " Web / company source は <strong>candidate information only</strong> です。"
      " 1000件母集団は全件深掘りしたわけではありません。"
    ),
    unsafe_allow_html=True,
  )

  source_mode = st.radio(
    "Sources 表示モード",
    options=["small demo sources", "large candidate population"],
    horizontal=True,
    key="v8_sources_mode",
  )

  if source_mode == "large candidate population":
    _render_large_candidate_sources(root=root, default_case=default_case)
    return

  base_table = load_sources_table(project_root=root)
  if not base_table.records:
    st.markdown(
      render_warning_box(
        "まだ Sources がありません。入力タブで案件を選ぶか、"
        " cases/*/source_candidates.csv を確認してください。"
      ),
      unsafe_allow_html=True,
    )
    st.markdown(
      render_next_action_box(f"まず「{V8_TAB_LABELS['input']}」で3案件サンプルを選択してください。"),
      unsafe_allow_html=True,
    )
    return

  case_options = _case_filter_options()
  case_ids = [cid for cid, _ in case_options]
  case_labels = {cid: label for cid, label in case_options}
  default_case_filter = default_case if default_case in case_ids else "all"

  col1, col2, col3 = st.columns(3)
  with col1:
    selected_case = st.selectbox(
      "案件",
      options=case_ids,
      index=case_ids.index(default_case_filter),
      format_func=lambda cid: case_labels[cid],
      key="v8_sources_case_filter",
    )
  if selected_case != "all":
    st.session_state[STATE_V8_SELECTED_CASE] = selected_case
  with col2:
    type_filter = st.selectbox(
      "source_type",
      options=["all", "patent", "paper", "web", "company", "manual", "unknown"],
      key="v8_sources_type_filter",
    )
  with col3:
    role_options = sorted({r.evidence_role for r in base_table.records})
    evidence_filter = st.selectbox(
      "evidence_role",
      options=["all", *role_options],
      key="v8_sources_role_filter",
    )

  col4, col5, col6 = st.columns(3)
  with col4:
    verification_filter = st.selectbox(
      "verification_status",
      options=["all", "unverified", "needs_human_review", "source_url_available"],
      key="v8_sources_verification_filter",
    )
  with col5:
    candidate_filter = st.selectbox(
      "candidate_information_only",
      options=["all", "only", "exclude"],
      key="v8_sources_candidate_filter",
    )
  with col6:
    search_text = st.text_input("検索（title / org / pub / notes）", key="v8_sources_search")

  candidate_only: bool | None = None
  if candidate_filter == "only":
    candidate_only = True
  elif candidate_filter == "exclude":
    candidate_only = False

  filtered = filter_sources_table(
    base_table,
    case_id=selected_case,
    source_type=type_filter,
    evidence_role=evidence_filter,
    verification_status=verification_filter,
    candidate_only=candidate_only,
    search_text=search_text,
  )

  patents = filtered.count_by_type.get("patent", 0)
  papers = filtered.count_by_type.get("paper", 0)
  web_company = filtered.count_by_type.get("web", 0) + filtered.count_by_type.get("company", 0)
  needs_review = sum(1 for r in filtered.records if r.human_review_required)
  candidate_only_count = sum(1 for r in filtered.records if r.candidate_information_only)

  m1, m2, m3, m4, m5, m6 = st.columns(6)
  m1.metric("total", filtered.source_count)
  m2.metric("patents", patents)
  m3.metric("papers", papers)
  m4.metric("web/company", web_company)
  m5.metric("human review", needs_review)
  m6.metric("candidate only", candidate_only_count)

  if patents == 0:
    st.markdown(
      render_warning_box("patent source が 0 件です。読むべき特許を作るには patent type の Sources が必要です。"),
      unsafe_allow_html=True,
    )

  if filtered.warnings:
    for warning in filtered.warnings:
      st.caption(f"warning: {warning}")

  if not filtered.records:
    st.info("フィルタ条件に一致する Sources がありません。")
    return

  df = pd.DataFrame([{col: getattr(r, col) for col in DISPLAY_COLUMNS} for r in filtered.records])
  st.dataframe(df, width="stretch", hide_index=True)

  st.markdown("#### 選択 source の詳細")
  titles = [f"{r.publication_number or r.title[:40]} ({r.source_id})" for r in filtered.records]
  selected_idx = st.selectbox("詳細を見る source", options=range(len(filtered.records)), format_func=lambda i: titles[i], key="v8_sources_detail_pick")
  detail = filtered.records[selected_idx]
  st.markdown(f"**{detail.title}**")
  st.markdown(f"- organization: {detail.organization}")
  st.markdown(f"- year: {detail.year}")
  st.markdown(f"- url: {detail.url or '（なし — human review required）'}")
  st.markdown(f"- publication_number: {detail.publication_number}")
  st.markdown(f"- doi: {detail.doi}")
  st.markdown(f"- evidence_role: {detail.evidence_role}")
  st.markdown(f"- reliability_label: {detail.reliability_label}")
  st.markdown(f"- verification_status: {detail.verification_status}")
  if detail.candidate_information_only:
    st.markdown(render_warning_box("candidate information only — 確定事実として扱いません。"), unsafe_allow_html=True)
  if detail.human_review_required:
    st.markdown(render_warning_box("human review required — 一次情報の人手確認が必要です。"), unsafe_allow_html=True)
  st.caption(detail.notes)

  case_name = resolve_case_name(selected_case, root)
  st.markdown("#### ダウンロード / Export Package")
  st.download_button(
    "CSV",
    data=records_to_csv_text(filtered.records).encode("utf-8"),
    file_name=f"sources_{selected_case}.csv",
    mime="text/csv",
    key="v8_sources_dl_csv",
  )
  st.download_button(
    "Markdown",
    data=records_to_markdown(filtered.records, case_name=case_name, table=filtered).encode("utf-8"),
    file_name=f"sources_{selected_case}.md",
    mime="text/markdown",
    key="v8_sources_dl_md",
  )

  if st.button("Export Package を生成", key="v8_sources_build_package", type="primary"):
    package = build_export_package(filtered, case_id=selected_case, project_root=root)
    st.session_state["v8_last_export_package"] = package.to_dict()
    st.success(f"Export Package を保存しました: {package.output_dir}")

  last_pkg = st.session_state.get("v8_last_export_package")
  if isinstance(last_pkg, dict) and last_pkg.get("output_dir"):
    st.caption(f"last package: {last_pkg.get('output_dir')}")
    xlsx_path = Path(str(last_pkg.get("sources_xlsx_path", "")))
    if xlsx_path.exists():
      st.download_button(
        "Excel (sources.xlsx)",
        data=xlsx_path.read_bytes(),
        file_name=xlsx_path.name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="v8_sources_dl_xlsx",
      )
    if last_pkg.get("excel_warning"):
      st.caption(str(last_pkg.get("excel_warning")))

  st.markdown(render_info_box(SAFETY_EXPORT_NOTICES[0]), unsafe_allow_html=True)
  st.markdown(
    render_next_action_box(f"次は「{V8_TAB_LABELS['patent_shortlist']}」で読むべき特許（Phase27D）を確認してください。"),
    unsafe_allow_html=True,
  )
