"""Top5 Deep Dive PDF pipeline UI (Phase 27S.4.1 / 27S.4.2)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from tech_cartography.runtime.v8_top5_pdf_pipeline_status_schema import (
  TOP5_PDF_PIPELINE_NOTICES,
  Top5PdfPipelineStatus,
)
from tech_cartography.services.v8_claim_example_binding import (
  bind_claims_to_example_facts,
  find_latest_claim_example_links_dir,
  write_claim_example_binding_outputs,
)
from tech_cartography.services.v8_gemini_example_facts import (
  export_gemini_prompts_only,
  extract_example_facts_from_sections,
  find_latest_patent_sections_output,
  write_example_facts_outputs,
)
from tech_cartography.services.v8_google_patents_links import build_google_patents_url
from tech_cartography.services.v8_llm_provider_gemini import (
  ENABLE_GEMINI_EXAMPLE_FACTS_ENV,
  gemini_availability_message,
  is_gemini_example_facts_enabled,
)
from tech_cartography.services.v8_patent_pdf_storage import (
  get_patent_pdf_upload_info,
  save_uploaded_patent_pdf,
)
from tech_cartography.services.v8_patent_pdf_text_extract import (
  extract_text_from_uploaded_top5_pdfs,
  write_pdf_text_outputs,
)
from tech_cartography.services.v8_patent_section_extract import (
  extract_sections_from_pdf_text_output,
  find_latest_pdf_text_extract_dir,
  find_publication_fulltext_raw_pack,
  find_latest_section_extract_dir,
  write_section_outputs,
)
from tech_cartography.ui.v8_google_vision_ocr_ui import render_google_vision_ocr_section
from tech_cartography.services.v8_top5_pdf_pipeline_status import (
  build_top5_pdf_pipeline_status,
)
from tech_cartography.ui.v8_judge_mode_copy import TOP5_DEEP_DIVE_WORKFLOW, TOP5_PDF_DEEP_DIVE_HELP
from tech_cartography.ui.v8_tab_config import V8_TAB_LABELS


def _session_pdf_uploads() -> dict[str, str]:
  raw = st.session_state.get("v8_patent_pdf_uploads")
  return dict(raw) if isinstance(raw, dict) else {}


def _metadata_from_top5_records(records: list | None) -> dict[str, dict[str, str]]:
  meta: dict[str, dict[str, str]] = {}
  if not records:
    return meta
  for r in records:
    pub = getattr(r, "publication_number", "") or ""
    if not pub:
      continue
    meta[pub] = {
      "title": getattr(r, "title", "") or "",
      "assignee": getattr(r, "organization", "") or getattr(r, "assignee", "") or "",
    }
  return meta


def _status_summary_rows(statuses: list[Top5PdfPipelineStatus]) -> list[dict]:
  rows = []
  for s in statuses:
    rows.append({
      "publication_number": s.publication_number,
      "pdf_uploaded": s.pdf_uploaded,
      "pdf_text_extracted": s.pdf_text_extracted,
      "needs_ocr": s.needs_ocr,
      "vision_ocr_text_extracted": s.vision_ocr_text_extracted,
      "text_extraction_method": s.text_extraction_method or "—",
      "sections_extracted": s.sections_extracted,
      "sections_from_ocr": s.sections_from_ocr,
      "sections_stale_vs_ocr": s.sections_stale_vs_ocr,
      "examples_count": s.examples_count,
      "example_facts_extracted": s.example_facts_extracted,
      "claim_example_links": s.claim_example_links_generated,
      "next_action": s.next_action,
    })
  return rows


def _default_upload_publication(statuses: list[Top5PdfPipelineStatus]) -> str:
  for s in statuses:
    if s.next_action == "PDFを取得してアップロード":
      return s.publication_number
  return statuses[0].publication_number


def render_top5_pdf_upload_section(
  statuses: list[Top5PdfPipelineStatus],
  case_id: str,
  project_root: Path,
  *,
  key_prefix: str = "v8_top5_dd",
) -> str:
  """Top5 PDF upload panel — always visible in Deep Dive."""
  st.markdown("**Top5公報PDFアップロード**")
  pubs = [s.publication_number for s in statuses]
  default_pub = _default_upload_publication(statuses)
  default_idx = pubs.index(default_pub) if default_pub in pubs else 0

  selected = st.selectbox(
    "PDF対象特許（Top5）",
    options=pubs,
    index=default_idx,
    key=f"{key_prefix}_pdf_pub_select",
  )

  gp_url = build_google_patents_url(selected)
  if gp_url:
    st.markdown(f"[Google Patentsで開く]({gp_url})")

  info = get_patent_pdf_upload_info(
    case_id, project_root, selected, session_uploads=_session_pdf_uploads(),
  )
  st.caption(
    f"publication_number: {info['publication_number']} / "
    f"status: {info['upload_status']} / "
    f"path: {info['pdf_path']} / "
    f"size: {info['file_size']:,} bytes"
  )

  pdf_file = st.file_uploader(
    "特許PDF（公報PDF）",
    type=["pdf"],
    key=f"{key_prefix}_pdf_file_{selected}",
  )
  if pdf_file is not None and st.button(
    "PDFを保存",
    key=f"{key_prefix}_pdf_save_{selected}",
    type="primary",
  ):
    try:
      save_uploaded_patent_pdf(
        case_id,
        project_root,
        selected,
        pdf_file.getvalue(),
        original_filename=pdf_file.name,
        allowed_publications=pubs,
      )
      uploads = _session_pdf_uploads()
      uploads[selected] = pdf_file.name
      st.session_state["v8_patent_pdf_uploads"] = uploads
      st.success("PDFを保存しました。次に Extract PDF text を実行してください。")
      st.rerun()
    except ValueError as exc:
      st.warning(str(exc))

  return selected


def _render_next_action_for_patent(
  status: Top5PdfPipelineStatus,
  case_id: str,
  project_root: Path,
  output_root: Path,
  *,
  key_prefix: str,
  show_upload_panel: bool = False,
) -> None:
  pub = status.publication_number
  st.caption(f"次の操作: **{status.next_action}**")
  if status.warning:
    st.caption(status.warning)

  if not status.pdf_uploaded:
    if show_upload_panel:
      st.info("上の「Top5公報PDFアップロード」で対象特許を選び、PDFを保存してください。")
    else:
      st.info("Top5 Deep Dive｜公報PDF解析 のアップロード欄でPDFを保存してください。")
    return

  if not status.pdf_text_extracted:
    if st.button("Extract PDF text", key=f"{key_prefix}_text_{pub}", type="primary"):
      results = extract_text_from_uploaded_top5_pdfs(case_id, project_root)
      write_pdf_text_outputs(case_id, results, output_root)
      st.success("PDF本文抽出を実行しました（Top5一括）")
      st.rerun()
    return

  if status.needs_ocr or status.vision_ocr_text_extracted:
    render_google_vision_ocr_section(
      status, case_id, project_root, output_root, key_prefix=key_prefix,
    )
    if status.needs_ocr and not status.vision_ocr_text_extracted:
      return

  needs_sections_from_ocr = (
    status.vision_ocr_text_extracted
    and (not status.sections_extracted or status.sections_stale_vs_ocr)
  )
  if needs_sections_from_ocr:
    return

  if not status.sections_extracted:
    pack = find_publication_fulltext_raw_pack(
      case_id, project_root, publication_number=pub, prefer_ocr=False,
    )
    raw_csv = pack.raw_csv_path if pack else None
    if raw_csv and raw_csv.exists() and st.button(
      "Extract sections", key=f"{key_prefix}_sec_{pub}", type="primary",
    ):
      results = extract_sections_from_pdf_text_output(case_id, raw_csv, output_root)
      write_section_outputs(case_id, results, output_root)
      method = pack.extraction_method if pack else "unknown"
      st.success(f"セクション抽出を実行しました（source: {method}）")
      st.rerun()
    elif not raw_csv:
      st.caption("publication_fulltext_raw.csv が見つかりません — PDF本文抽出またはOCRを先に実行してください。")
    return

  if status.sections_extracted and not status.has_examples and (status.examples_count or 0) == 0:
    st.info(
      "examples / comparative examples / tables が検出されていません。"
      " 公報の表記ゆれ、翻訳PDF、画像PDF、または実施例見出しの違いの可能性があります。"
    )
    if status.fallback_used:
      st.caption("embodiments を fallback 候補として Gemini プロンプトに含めます。")
    st.caption(f"対象セクション数: {status.target_sections_count} / types: {status.target_section_types or '—'}")

  if not status.example_facts_extracted:
    if not is_gemini_example_facts_enabled():
      st.warning(
        "Gemini実行は現在OFFです。抽出プロンプトをExportするか、"
        f" 環境変数 {ENABLE_GEMINI_EXAMPLE_FACTS_ENV}=true を設定して再起動してください。"
      )
      sections_dir = find_latest_patent_sections_output(case_id, output_root)
      sections_csv = (sections_dir / "publication_fulltext_sections.csv") if sections_dir else None
      if sections_csv and sections_csv.exists() and st.button(
        "Export Gemini prompts", key=f"{key_prefix}_prompts_{pub}", type="primary",
      ):
        export_gemini_prompts_only(case_id, sections_csv, output_root, project_root)
        st.success("Geminiプロンプトを出力しました")
      with st.expander("開発者向け: Gemini有効化", expanded=False):
        st.code(f"export {ENABLE_GEMINI_EXAMPLE_FACTS_ENV}=true\nstreamlit run app.py", language="bash")
        st.caption(gemini_availability_message())
    else:
      sections_dir = find_latest_patent_sections_output(case_id, output_root)
      sections_csv = (sections_dir / "publication_fulltext_sections.csv") if sections_dir else None
      if sections_csv and sections_csv.exists() and st.button(
        "Extract example facts with Gemini", key=f"{key_prefix}_facts_{pub}", type="primary",
      ):
        results, prompts, vocab = extract_example_facts_from_sections(
          case_id, sections_csv, output_root, project_root, use_gemini=True,
        )
        write_example_facts_outputs(case_id, results, output_root, vocab, prompts)
        st.success("実施例ファクト抽出を実行しました（Top5一括）")
        st.rerun()
    return

  if not status.claim_example_links_generated:
    if st.button("Bind claim to example facts", key=f"{key_prefix}_bind_{pub}", type="primary"):
      results = bind_claims_to_example_facts(case_id, project_root, output_root)
      write_claim_example_binding_outputs(case_id, results, output_root)
      st.success("Claim-Example対応候補を生成しました（Top5一括）")
      st.rerun()
    return

  st.success(
    f"対応候補あり — linked={status.linked_claim_count}, unlinked={status.unlinked_claim_count}。"
    " 次: Gapロジック更新へ（次Phase）"
  )


def render_top5_pdf_deep_dive_section(
  case_id: str,
  project_root: Path,
  *,
  top5_records: list | None = None,
  key_prefix: str = "v8_top5_dd",
) -> None:
  st.markdown("#### Top5 Deep Dive｜公報PDF解析")
  st.caption(TOP5_DEEP_DIVE_WORKFLOW)
  st.caption(TOP5_PDF_DEEP_DIVE_HELP)
  for notice in TOP5_PDF_PIPELINE_NOTICES:
    st.caption(notice)

  output_root = project_root / "outputs"
  meta = _metadata_from_top5_records(top5_records)
  statuses = build_top5_pdf_pipeline_status(
    case_id, project_root, output_root, metadata_by_pub=meta,
  )

  if not statuses:
    st.caption("Top5 未生成 — Generate Reading Priority を実行してください。")
    return

  st.markdown("**Top5 PDF Pipeline Summary**")
  st.dataframe(pd.DataFrame(_status_summary_rows(statuses)), width="stretch", hide_index=True)

  render_top5_pdf_upload_section(statuses, case_id, project_root, key_prefix=key_prefix)

  pending = [s for s in statuses if s.next_action != "Gapロジック更新へ進めます"]
  focus = pending[0] if pending else statuses[0]
  st.markdown(f"**次に進める特許: {focus.publication_number}**")
  if focus.title or focus.assignee:
    st.caption(f"{focus.title[:80] if focus.title else '—'} / {focus.assignee or '—'}")
  _render_next_action_for_patent(
    focus, case_id, project_root, output_root,
    key_prefix=key_prefix, show_upload_panel=True,
  )

  with st.expander("Top5 各特許の詳細・操作", expanded=False):
    for status in statuses:
      with st.expander(f"{status.publication_number} — {status.next_action}", expanded=False):
        st.caption(f"title: {(status.title or '—')[:100]}")
        st.caption(f"assignee: {status.assignee or '—'}")
        if status.google_patents_url:
          st.markdown(f"[Google Patentsで開く]({status.google_patents_url})")
        _render_next_action_for_patent(
          status, case_id, project_root, output_root,
          key_prefix=f"{key_prefix}_{status.publication_number}",
          show_upload_panel=True,
        )

  with st.expander("出力ダウンロード・開発者向け詳細", expanded=False):
    text_dir = find_latest_pdf_text_extract_dir(case_id, project_root)
    sec_dir = find_latest_section_extract_dir(case_id, project_root)
    bind_dir = find_latest_claim_example_links_dir(case_id, project_root)
    ocr_pack = find_publication_fulltext_raw_pack(
      case_id, project_root, prefer_ocr=True,
    )
    text_method = ocr_pack.extraction_method if ocr_pack else ""
    if ocr_pack:
      st.caption(f"現在の本文抽出方法: {text_method} ({ocr_pack.pack_dir})")
    for label, path in (
      ("OCR pack", ocr_pack.pack_dir if ocr_pack else None),
      ("PDF text", text_dir),
      ("Sections", sec_dir),
      ("Claim-example links", bind_dir),
    ):
      if path and path.exists():
        st.caption(f"{label}: {path}")
    st.caption(f"語彙編集: 「{V8_TAB_LABELS['input']}」タブの抽出フォーカス語彙")
