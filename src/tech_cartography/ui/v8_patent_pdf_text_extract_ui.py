"""Patent PDF text extraction UI (Phase 27S.1)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from tech_cartography.runtime.v8_patent_pdf_text_schema import PDF_TEXT_EXTRACTION_NOTICES
from tech_cartography.services.v8_large_candidate_shortlist import load_top5_publications
from tech_cartography.services.v8_patent_pdf_text_extract import (
  _pypdf_available,
  extract_text_from_uploaded_top5_pdfs,
  find_latest_pdf_text_extract_dir,
  find_uploaded_patent_pdfs,
  get_pdf_pipeline_status,
  infer_publication_number_from_pdf_path,
  load_extraction_summary_from_dir,
  write_pdf_text_outputs,
)
from tech_cartography.ui.v8_judge_mode_copy import PDF_TEXT_EXTRACT_HELP


def render_pdf_text_extraction_caution() -> None:
  for notice in PDF_TEXT_EXTRACTION_NOTICES:
    st.caption(notice)


def _session_key(case_id: str) -> str:
  return f"v8_pdf_text_extract_{case_id}"


def render_top5_pdf_text_extract_section(
  case_id: str,
  project_root: Path,
  *,
  key_prefix: str = "vGET",
) -> None:
  st.markdown("#### Top5公報PDF テキスト抽出")
  st.caption(PDF_TEXT_EXTRACT_HELP)
  render_pdf_text_extraction_caution()

  if not _pypdf_available():
    st.warning("PDF抽出ライブラリ（pypdf）が未導入です — `pip install pypdf` でインストールしてください。")

  pdfs = find_uploaded_patent_pdfs(case_id, project_root)
  top5 = load_top5_publications(case_id, project_root)
  latest_dir = find_latest_pdf_text_extract_dir(case_id, project_root)
  summary = load_extraction_summary_from_dir(latest_dir) if latest_dir else {}

  rows = []
  for pub in top5:
    status = get_pdf_pipeline_status(case_id, pub, project_root)
    pdf_path = project_root / "cases" / case_id / "patent_pdfs" / f"{pub}.pdf"
    row = summary.get(pub, {})
    rows.append({
      "publication_number": pub,
      "PDF保存場所": str(pdf_path) if pdf_path.exists() else "—",
      "pdf_uploaded": status["pdf_uploaded"],
      "抽出ステータス": row.get("status") or ("未抽出" if status["pdf_uploaded"] else "PDF未アップロード"),
      "text_length": status["total_text_length"],
      "needs_ocr": status["needs_ocr"],
    })

  for pdf in pdfs:
    pub = infer_publication_number_from_pdf_path(pdf)
    if pub in top5:
      continue
    status = get_pdf_pipeline_status(case_id, pub, project_root)
    row = summary.get(pub, {})
    rows.append({
      "publication_number": pub,
      "PDF保存場所": str(pdf),
      "pdf_uploaded": True,
      "抽出ステータス": row.get("status") or "未抽出",
      "text_length": status["total_text_length"],
      "needs_ocr": status["needs_ocr"],
    })

  if not rows:
    st.caption("アップロード済みPDFはありません — 上のPDFアップロード欄から保存してください。")
  else:
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

  col1, col2 = st.columns(2)
  with col1:
    if st.button("Extract PDF text", key=f"{key_prefix}_extract", type="primary"):
      results = extract_text_from_uploaded_top5_pdfs(case_id, project_root)
      out_dir = write_pdf_text_outputs(case_id, results, project_root / "outputs")
      st.session_state[_session_key(case_id)] = {
        "output_dir": str(out_dir),
        "results": [r.to_dict() for r in results],
      }
      st.success(f"抽出完了 — {out_dir}")
  with col2:
    if st.button("Export extracted text", key=f"{key_prefix}_export"):
      cached = st.session_state.get(_session_key(case_id))
      if cached and cached.get("output_dir"):
        st.info(f"最新出力: {cached['output_dir']}")
      elif latest_dir:
        st.info(f"最新出力: {latest_dir}")
      else:
        st.caption("先に Extract PDF text を実行してください。")

  cached = st.session_state.get(_session_key(case_id))
  export_dir = Path(str(cached.get("output_dir", ""))) if cached else latest_dir
  if export_dir and export_dir.exists():
    st.caption(f"出力先: {export_dir}")
    files = [
      "publication_fulltext_raw.csv",
      "publication_fulltext_raw.md",
      "pdf_text_extraction_summary.csv",
      "pdf_text_extraction_summary.md",
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


def render_gap_pdf_extraction_status(
  case_id: str,
  project_root: Path,
  publication_numbers: list[str] | None = None,
) -> None:
  """Gap tab: PDF upload / extract status for example_support_missing guidance."""
  pubs = publication_numbers or load_top5_publications(case_id, project_root)
  if not pubs:
    return

  st.markdown("**Top5公報PDF — 抽出状況**")
  for pub in pubs:
    status = get_pdf_pipeline_status(case_id, pub, project_root)
    if not status["pdf_uploaded"]:
      line = f"- **{pub}**: PDF未アップロード — Google PatentsからPDF取得が必要"
    elif not status["text_extracted"]:
      line = f"- **{pub}**: PDFアップロード済み・本文未抽出 — 入力タブで Extract PDF text を実行"
    elif status["needs_ocr"]:
      line = f"- **{pub}**: needs_ocr=True — 画像PDFの可能性。将来OCR対象"
    else:
      line = f"- **{pub}**: PDF本文抽出済み — 次Phaseで examples / comparative examples を抽出"
    st.markdown(line)

  st.caption(
    "セクション抽出は入力タブの「Top5公報PDF セクション抽出」で実行できます。"
    " 実施例条件・物性値の構造化は Phase27S.3 で行います。"
  )
