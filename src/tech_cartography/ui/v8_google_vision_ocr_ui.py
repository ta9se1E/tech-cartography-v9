"""Google Vision OCR UI (Phase 27S.5 / 27S.5.1)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from tech_cartography.runtime.v8_google_vision_ocr_schema import GOOGLE_VISION_OCR_NOTICES
from tech_cartography.runtime.v8_top5_pdf_pipeline_status_schema import Top5PdfPipelineStatus
from tech_cartography.services.v8_google_vision_ocr import (
  ENABLE_GOOGLE_VISION_OCR_ENV,
  find_latest_google_vision_ocr_dir,
  find_vision_ocr_raw_json_dir,
  get_ocr_bucket_name,
  get_ocr_max_pages,
  is_google_vision_ocr_enabled,
  reparse_existing_vision_ocr_output,
  resolve_pdf_path_for_ocr,
  run_google_vision_ocr_for_pdf,
  vision_ocr_availability_message,
)
from tech_cartography.services.v8_patent_section_extract import (
  extract_sections_from_pdf_text_output,
  find_latest_publication_fulltext_raw_pack,
  write_section_outputs,
)
from tech_cartography.ui.v8_judge_mode_copy import GOOGLE_VISION_OCR_HELP


def _ocr_pack_dir(case_id: str, project_root: Path) -> Path | None:
  return find_latest_google_vision_ocr_dir(case_id, project_root)


def _render_extract_sections_from_ocr(
  case_id: str,
  project_root: Path,
  output_root: Path,
  pub: str,
  *,
  key_prefix: str,
) -> None:
  if st.button(
    "Extract sections from OCR text",
    key=f"{key_prefix}_sec_from_ocr_{pub}",
    type="primary",
  ):
    pack_dir, method = find_latest_publication_fulltext_raw_pack(case_id, project_root)
    raw_csv = (pack_dir / "publication_fulltext_raw.csv") if pack_dir else None
    if raw_csv and raw_csv.exists():
      results = extract_sections_from_pdf_text_output(case_id, raw_csv, output_root)
      write_section_outputs(case_id, results, output_root)
      st.success(f"セクション抽出を実行しました（source: {method}）")
      st.rerun()


def render_google_vision_ocr_section(
  status: Top5PdfPipelineStatus,
  case_id: str,
  project_root: Path,
  output_root: Path,
  *,
  key_prefix: str,
  show_section_extract: bool = True,
) -> None:
  """OCR panel for needs_ocr patents in Top5 Deep Dive."""
  pub = status.publication_number
  if not status.needs_ocr and not status.vision_ocr_text_extracted:
    return

  st.markdown("**Google Vision OCR（画像PDFフォールバック）**")
  st.caption(GOOGLE_VISION_OCR_HELP)
  for notice in GOOGLE_VISION_OCR_NOTICES[:2]:
    st.caption(notice)

  pdf_path = status.pdf_path or str(resolve_pdf_path_for_ocr(case_id, pub, project_root))
  st.caption(f"OCR対象: {pub} / PDF: {pdf_path}")
  st.caption(f"needs_ocr: {status.needs_ocr} / OCR利用可能: {status.vision_ocr_available}")
  st.caption(f"GCS bucket: {get_ocr_bucket_name() or '（未設定）'} / max_pages: {get_ocr_max_pages()}")

  ocr_pack = _ocr_pack_dir(case_id, project_root)
  raw_json_dir = find_vision_ocr_raw_json_dir(ocr_pack) if ocr_pack else None
  if raw_json_dir:
    json_count = len(list(raw_json_dir.glob("*.json")))
    st.caption(f"raw_vision_json: {json_count} files ({raw_json_dir})")
    if st.button(
      "Rebuild OCR CSV from existing raw JSON",
      key=f"{key_prefix}_reparse_{pub}",
    ):
      if ocr_pack:
        result = reparse_existing_vision_ocr_output(
          ocr_pack, case_id, pub,
          source_pdf_path=Path(pdf_path) if pdf_path else None,
          project_root=project_root,
        )
        if result.status in {"ocr_completed", "success"} and result.extracted_pages > 0:
          st.success(
            f"OCR出力を再生成しました — pages={result.extracted_pages}, chars={result.total_text_length}"
          )
          st.rerun()
        else:
          st.error(f"再生成失敗 — status={result.status}, warning={result.warning}")

  if status.vision_ocr_text_extracted:
    pages = status.vision_ocr_extracted_pages or "—"
    chars = status.vision_ocr_total_text_length or 0
    st.success(
      f"OCR本文取得済み — pages={pages}, chars={chars}, "
      f"status={status.vision_ocr_status or 'ocr_completed'}"
    )
    st.caption("OCR結果は自動抽出テキストであり、誤読の可能性があります。実施例・数値・単位は必ず原文確認してください。")
    if show_section_extract and not status.sections_extracted:
      _render_extract_sections_from_ocr(
        case_id, project_root, output_root, pub, key_prefix=key_prefix,
      )
    return

  if not status.needs_ocr:
    return

  st.info("通常のPDF本文抽出では文字量が不足しています。Google Vision OCRで本文抽出できます。")

  if not is_google_vision_ocr_enabled():
    st.warning(
      f"Google Vision OCRは現在OFFです。"
      f" {ENABLE_GOOGLE_VISION_OCR_ENV}=true と GCS bucket を設定して再起動してください。"
    )
    with st.expander("開発者向け: OCR有効化", expanded=False):
      st.code(
        f"export {ENABLE_GOOGLE_VISION_OCR_ENV}=true\n"
        f"export GOOGLE_VISION_OCR_GCS_BUCKET=your-bucket\n"
        "streamlit run app.py",
        language="bash",
      )
      st.caption(vision_ocr_availability_message())
    return

  if not get_ocr_bucket_name():
    st.warning("OCR用GCS bucketが未設定です。GOOGLE_VISION_OCR_GCS_BUCKET を設定してください。")
    return

  st.caption(vision_ocr_availability_message())
  st.warning("OCR実行にはGCP費用と数分かかる場合があります。1件ずつ実行してください。")

  if st.button(
    "Run Google Vision OCR",
    key=f"{key_prefix}_run_ocr_{pub}",
    type="primary",
  ):
    with st.spinner(f"Google Vision OCR 実行中 — {pub}..."):
      result = run_google_vision_ocr_for_pdf(
        case_id,
        pub,
        Path(pdf_path),
        output_root,
      )
    if result.status in {"success", "ocr_completed"} and result.total_text_length > 0:
      st.success(
        f"OCR完了 — pages={result.extracted_pages}, chars={result.total_text_length}"
      )
      st.caption(f"output: {result.output_dir}")
      st.rerun()
    else:
      st.error(f"OCR失敗 — status={result.status}, warning={result.warning}")

  pack_dir, method = find_latest_publication_fulltext_raw_pack(case_id, project_root)
  if pack_dir:
    st.caption(f"現在の本文抽出方法: {method} ({pack_dir})")
