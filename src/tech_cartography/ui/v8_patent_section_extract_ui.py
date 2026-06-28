"""Patent fulltext section extraction UI (Phase 27S.2)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from tech_cartography.runtime.v8_patent_section_schema import SECTION_EXTRACTION_NOTICES
from tech_cartography.services.v8_large_candidate_shortlist import load_top5_publications
from tech_cartography.services.v8_patent_pdf_text_extract import find_latest_pdf_text_extract_dir
from tech_cartography.services.v8_patent_section_extract import (
  extract_sections_from_pdf_text_output,
  find_latest_pdf_text_extract_output,
  find_latest_section_extract_dir,
  get_combined_patent_pdf_pipeline_status,
  load_section_summary_from_dir,
  write_section_outputs,
)
from tech_cartography.ui.v8_judge_mode_copy import PDF_SECTION_EXTRACT_HELP


def _session_key(case_id: str) -> str:
  return f"v8_patent_sections_{case_id}"


def render_section_extraction_caution() -> None:
  for notice in SECTION_EXTRACTION_NOTICES:
    st.caption(notice)


def render_top5_pdf_section_extract_section(
  case_id: str,
  project_root: Path,
  *,
  key_prefix: str = "v8_psec",
) -> None:
  st.markdown("#### Top5公報PDF セクション抽出")
  st.caption(PDF_SECTION_EXTRACT_HELP)
  render_section_extraction_caution()

  output_root = project_root / "outputs"
  latest_text_dir = find_latest_pdf_text_extract_dir(case_id, project_root)
  raw_csv = (latest_text_dir / "publication_fulltext_raw.csv") if latest_text_dir else None
  latest_section_dir = find_latest_section_extract_dir(case_id, project_root)
  section_summary = load_section_summary_from_dir(latest_section_dir) if latest_section_dir else {}

  if latest_text_dir and raw_csv and raw_csv.exists():
    st.caption(f"最新PDF本文抽出: {latest_text_dir}")
  else:
    st.caption("PDF本文抽出結果がありません — 上の「Extract PDF text」を先に実行してください。")

  top5 = load_top5_publications(case_id, project_root)
  rows = []
  for pub in top5:
    pipe = get_combined_patent_pdf_pipeline_status(case_id, pub, project_root)
    sec = section_summary.get(pub, {})
    rows.append({
      "publication_number": pub,
      "text_extracted": pipe.get("text_extracted"),
      "sections_extracted": pipe.get("sections_extracted"),
      "section_count": sec.get("section_count", "—"),
      "examples_count": sec.get("examples_count", pipe.get("examples_count", 0)),
      "comparative_examples_count": sec.get("comparative_examples_count", 0),
      "tables_count": sec.get("tables_count", 0),
      "has_examples": sec.get("has_examples", pipe.get("has_examples")),
      "needs_human_review": sec.get("needs_human_review", pipe.get("section_needs_human_review")),
    })

  if rows:
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
  else:
    st.caption("Top5 未生成 — Generate Reading Priority を実行してください。")

  col1, col2 = st.columns(2)
  with col1:
    extract_disabled = not (raw_csv and raw_csv.exists())
    if st.button(
      "Extract sections",
      key=f"{key_prefix}_extract",
      type="primary",
      disabled=extract_disabled,
    ):
      results = extract_sections_from_pdf_text_output(case_id, raw_csv, output_root)
      out_dir = write_section_outputs(case_id, results, output_root)
      st.session_state[_session_key(case_id)] = {"output_dir": str(out_dir)}
      st.success(f"セクション抽出完了 — {out_dir}")
  with col2:
    cached = st.session_state.get(_session_key(case_id))
    export_dir = Path(str(cached.get("output_dir", ""))) if cached else latest_section_dir
    if export_dir and export_dir.exists():
      st.caption(f"出力先: {export_dir}")
    else:
      st.caption("先に Extract sections を実行してください。")

  cached = st.session_state.get(_session_key(case_id))
  export_dir = Path(str(cached.get("output_dir", ""))) if cached else latest_section_dir
  if export_dir and export_dir.exists():
    files = [
      "publication_fulltext_sections.csv",
      "publication_fulltext_sections.md",
      "section_extraction_summary.csv",
      "section_extraction_summary.md",
    ]
    cols = st.columns(2)
    for idx, name in enumerate(files):
      path = export_dir / name
      if path.exists():
        cols[idx % 2].download_button(
          name,
          path.read_bytes(),
          name,
          key=f"{key_prefix}_dl_{name}",
        )


def render_gap_section_extraction_status(
  case_id: str,
  project_root: Path,
  publication_numbers: list[str] | None = None,
) -> None:
  pubs = publication_numbers or load_top5_publications(case_id, project_root)
  if not pubs:
    return

  st.markdown("**Top5公報PDF — 解析パイプライン状況**")
  for pub in pubs:
    pipe = get_combined_patent_pdf_pipeline_status(case_id, pub, project_root)
    if not pipe["pdf_uploaded"]:
      line = f"- **{pub}**: PDF未アップロード — Google PatentsからPDF取得が必要"
    elif not pipe["text_extracted"]:
      line = f"- **{pub}**: PDFアップロード済み・本文未抽出 — Extract PDF text が必要"
    elif not pipe.get("sections_extracted"):
      line = f"- **{pub}**: 本文抽出済み・examples未抽出 — Extract sections が必要"
    elif pipe.get("section_needs_human_review"):
      line = f"- **{pub}**: needs_human_review=True — セクション判定の人手確認が必要"
    elif pipe.get("has_examples"):
      line = f"- **{pub}**: examples抽出済み — 次Phaseで Example facts 抽出へ"
    else:
      line = f"- **{pub}**: セクション抽出済み — examples未検出、人手確認を推奨"
    st.markdown(line)

  st.caption(
    "セクション判定は候補です。実施例条件・物性値の構造化は Phase27S.3 で行います。"
  )
