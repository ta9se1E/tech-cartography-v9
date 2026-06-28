"""Top5 PDF pipeline status aggregator (Phase 27S.4.1) — read-only."""

from __future__ import annotations

import csv
from pathlib import Path

from tech_cartography.runtime.v8_research_theme_schema import normalize_publication_number
from tech_cartography.runtime.v8_top5_pdf_pipeline_status_schema import Top5PdfPipelineStatus
from tech_cartography.services.v8_claim_example_binding import (
  find_latest_claim_example_links_dir,
  load_binding_summary_from_dir,
)
from tech_cartography.services.v8_evidence_gap_next_actions import (
  load_evidence_gap_summary_by_pub,
)
from tech_cartography.services.v8_gemini_example_facts import (
  find_latest_example_facts_dir,
  load_example_facts_summary_from_dir,
  load_target_sections,
)
from tech_cartography.services.v8_google_vision_ocr import (
  find_latest_google_vision_ocr_dir,
  get_ocr_bucket_name,
  is_google_vision_ocr_enabled,
  load_ocr_summary_from_dir,
  load_vision_ocr_raw_csv_stats,
)
from tech_cartography.services.v8_google_patents_links import (
  build_google_patents_url,
  patent_pdfs_dir,
  resolve_pdf_upload_status,
)
from tech_cartography.services.v8_large_candidate_shortlist import load_top5_publications
from tech_cartography.services.v8_patent_pdf_text_extract import (
  find_latest_pdf_text_extract_dir,
  load_extraction_summary_from_dir,
)
from tech_cartography.services.v8_patent_section_extract import (
  find_latest_section_extract_dir,
  load_section_summary_from_dir,
  sections_stale_vs_ocr_output,
)
from tech_cartography.services.v8_sources_table import project_root_from_here


def _project_root_from_output(output_root: Path) -> Path:
  return output_root.parent if output_root.name == "outputs" else output_root


def find_latest_pdf_text_summary(case_id: str, output_root: Path | str) -> Path | None:
  root = _project_root_from_output(Path(output_root))
  latest = find_latest_pdf_text_extract_dir(case_id, root)
  if latest and (latest / "pdf_text_extraction_summary.csv").exists():
    return latest / "pdf_text_extraction_summary.csv"
  return None


def find_latest_section_summary(case_id: str, output_root: Path | str) -> Path | None:
  root = _project_root_from_output(Path(output_root))
  latest = find_latest_section_extract_dir(case_id, root)
  if latest and (latest / "section_extraction_summary.csv").exists():
    return latest / "section_extraction_summary.csv"
  return None


def find_latest_example_facts_summary(case_id: str, output_root: Path | str) -> Path | None:
  root = _project_root_from_output(Path(output_root))
  latest = find_latest_example_facts_dir(case_id, root)
  if latest and (latest / "example_facts_summary.csv").exists():
    return latest / "example_facts_summary.csv"
  return None


def find_latest_claim_example_binding_summary(case_id: str, output_root: Path | str) -> Path | None:
  root = _project_root_from_output(Path(output_root))
  latest = find_latest_claim_example_links_dir(case_id, root)
  if latest and (latest / "claim_example_binding_summary.csv").exists():
    return latest / "claim_example_binding_summary.csv"
  return None


def _int_or_none(value: object) -> int | None:
  if value is None or value == "":
    return None
  try:
    return int(value)
  except (TypeError, ValueError):
    return None


def _bool_from_row(value: object) -> bool:
  return str(value).lower() in {"true", "1", "yes"} or value is True


def _target_section_info_for_pub(
  sections_csv: Path | None,
  publication_number: str,
) -> tuple[int, str, bool]:
  if not sections_csv or not sections_csv.exists():
    return 0, "", False
  all_targets = load_target_sections(sections_csv)
  pub = normalize_publication_number(publication_number)
  targets = [r for r in all_targets if normalize_publication_number(str(r.get("publication_number", ""))) == pub]
  types = sorted({str(r.get("section_type") or "") for r in targets if r.get("section_type")})
  fallback = bool(targets) and "embodiments" in types and not any(
    str(r.get("section_type")) in {"examples", "comparative_examples", "tables"} for r in targets
  )
  return len(targets), ",".join(types), fallback


def infer_pipeline_status_label(status: Top5PdfPipelineStatus) -> tuple[str, str]:
  details: list[str] = []
  if status.vision_ocr_text_extracted:
    details.append("OCR completed")
  if status.sections_extracted:
    details.append("sections extracted")
  if status.example_facts_extracted:
    details.append("example facts extracted")
  if status.claim_example_links_generated:
    details.append("claim-example binding generated")
  if status.evidence_aware_gaps_generated:
    details.append("evidence-aware gaps generated")

  if status.evidence_ready_for_review:
    return "Review-ready candidate", " / ".join(details) if details else "review-ready candidate"
  if status.evidence_no_example_facts:
    if status.pdf_uploaded and not status.vision_ocr_text_extracted and status.needs_ocr:
      return "PDF uploaded / OCR or text extraction pending", " / ".join(details) if details else ""
    if status.vision_ocr_text_extracted and not status.sections_extracted:
      return "OCR text available / sections pending", " / ".join(details) if details else ""
    if status.sections_extracted and not status.example_facts_extracted:
      return "text or sections available / example facts pending", " / ".join(details) if details else ""
    return "example facts pending", " / ".join(details) if details else ""
  if status.claim_example_links_generated and status.evidence_aware_gaps_generated:
    return "Evidence-aware gaps generated", " / ".join(details) if details else ""
  if not status.pdf_uploaded:
    return "PDF not uploaded", ""
  if status.needs_ocr and not status.vision_ocr_text_extracted:
    return "PDF uploaded / OCR or text extraction pending", ""
  if status.vision_ocr_text_extracted and not status.sections_extracted:
    return "OCR text available / sections pending", ""
  if status.sections_extracted and not status.example_facts_extracted:
    return "text or sections available / example facts pending", ""
  return "pipeline in progress", " / ".join(details) if details else ""


def infer_next_action(status: Top5PdfPipelineStatus) -> str:
  if not status.pdf_uploaded:
    return "PDFを取得してアップロード"
  if not status.pdf_text_extracted and not status.vision_ocr_text_extracted:
    return "Extract PDF text"
  if status.needs_ocr and not status.vision_ocr_text_extracted:
    if not status.vision_ocr_available:
      return "OCR disabled: enable Google Vision OCR"
    return "Run Google Vision OCR or verify PDF text extraction"
  if status.vision_ocr_text_extracted and (
    not status.sections_extracted or status.sections_stale_vs_ocr
  ):
    return "Extract sections from OCR text"
  if not status.sections_extracted:
    return "Extract sections"
  if not status.example_facts_extracted:
    if status.sections_extracted and not status.has_examples and (status.examples_count or 0) == 0:
      return "examples未検出: セクション抽出結果を確認してください"
    return "Extract example facts or review sections"
  if not status.claim_example_links_generated:
    return "Bind claim to example facts"
  if status.evidence_ready_for_review:
    return "PDF原文でOCR由来の工程条件・物性値・表候補を確認"
  if status.evidence_aware_gaps_generated:
    return "Claim-Example evidence-aware Gap generated — human review checklist available"
  return "Generate evidence-aware Gap / Next Actions from Claim-Example binding"


def build_top5_pdf_pipeline_status(
  case_id: str,
  project_root: Path | str,
  output_root: Path | str,
  *,
  metadata_by_pub: dict[str, dict[str, str]] | None = None,
) -> list[Top5PdfPipelineStatus]:
  root = Path(project_root)
  out = Path(output_root)
  pubs = load_top5_publications(case_id, root)
  meta = metadata_by_pub or {}

  pdf_dir = find_latest_pdf_text_extract_dir(case_id, root)
  pdf_summary = load_extraction_summary_from_dir(pdf_dir) if pdf_dir else {}

  ocr_dir = find_latest_google_vision_ocr_dir(case_id, root)
  ocr_summary = load_ocr_summary_from_dir(ocr_dir) if ocr_dir else {}
  ocr_available = is_google_vision_ocr_enabled() and bool(get_ocr_bucket_name())

  section_dir = find_latest_section_extract_dir(case_id, root)
  section_summary = load_section_summary_from_dir(section_dir) if section_dir else {}

  facts_dir = find_latest_example_facts_dir(case_id, root)
  facts_summary = load_example_facts_summary_from_dir(facts_dir) if facts_dir else {}

  bind_dir = find_latest_claim_example_links_dir(case_id, root)
  bind_summary = load_binding_summary_from_dir(bind_dir) if bind_dir else {}

  evidence_gap_summary = load_evidence_gap_summary_by_pub(case_id, root)

  sections_csv = (section_dir / "publication_fulltext_sections.csv") if section_dir else None

  statuses: list[Top5PdfPipelineStatus] = []
  for pub in pubs:
    norm = normalize_publication_number(pub)
    m = meta.get(norm, {})
    uploaded = resolve_pdf_upload_status(norm, case_id=case_id, project_root=root) == "アップロード済み"
    pdf_path = patent_pdfs_dir(case_id, root) / f"{norm}.pdf"
    pdf_row = pdf_summary.get(norm, {})
    ocr_row = ocr_summary.get(norm, {})
    sec_row = section_summary.get(norm, {})
    fact_row = facts_summary.get(norm, {})
    bind_row = bind_summary.get(norm, {})

    text_extracted = bool(pdf_row) and str(pdf_row.get("status", "")) not in {"", "file_missing"}
    needs_ocr = _bool_from_row(pdf_row.get("needs_ocr")) if pdf_row else False
    ocr_status = str(ocr_row.get("status") or "") if ocr_row else ""
    ocr_raw_csv = (ocr_dir / "publication_fulltext_raw.csv") if ocr_dir else None
    raw_stats = (
      load_vision_ocr_raw_csv_stats(ocr_raw_csv, norm)
      if ocr_raw_csv and ocr_raw_csv.exists()
      else {"extracted": False, "rows": 0, "total_text_length": 0}
    )
    vision_ocr_extracted = bool(
      (ocr_row and ocr_status in {"success", "ocr_completed"} and _int_or_none(ocr_row.get("total_text_length", 0)) not in {None, 0})
      or raw_stats.get("extracted")
    )
    vision_ocr_len = (
      _int_or_none(ocr_row.get("total_text_length"))
      if ocr_row and _int_or_none(ocr_row.get("total_text_length"))
      else _int_or_none(raw_stats.get("total_text_length"))
    )
    vision_ocr_pages = (
      _int_or_none(ocr_row.get("extracted_pages"))
      if ocr_row and _int_or_none(ocr_row.get("extracted_pages"))
      else _int_or_none(raw_stats.get("rows"))
    )
    text_method = None
    if vision_ocr_extracted:
      text_method = "google_vision_ocr"
    elif text_extracted and not needs_ocr:
      text_method = str(pdf_row.get("extraction_method") or "pypdf")
    elif text_extracted:
      text_method = "pypdf"
    sections_extracted = bool(sec_row) and str(sec_row.get("status", "")) not in {"", "empty_input"}
    sections_from_ocr = sections_extracted and (
      "local_v8_google_vision_ocr" in str(sec_row.get("source_raw_csv") or "")
      or "google_vision_ocr" in str(sec_row.get("source_raw_csv") or "")
    )
    sections_stale = sections_stale_vs_ocr_output(sec_row if sec_row else None, section_dir, ocr_dir)
    has_description = _bool_from_row(sec_row.get("has_description")) if sec_row else False
    examples_count = _int_or_none(sec_row.get("examples_count")) if sec_row else 0
    has_examples = _bool_from_row(sec_row.get("has_examples")) if sec_row else False
    fact_count = _int_or_none(fact_row.get("fact_count")) if fact_row else 0
    facts_extracted = bool(fact_row) and fact_count and fact_count > 0
    links_generated = bool(bind_row) and _int_or_none(bind_row.get("link_count", 0)) not in {None, 0}

    gap_row = evidence_gap_summary.get(norm, {})
    evidence_gaps_generated = bool(gap_row)
    evidence_ready = _int_or_none(gap_row.get("ready_for_human_review_count")) not in {None, 0}
    evidence_no_facts = _int_or_none(gap_row.get("no_example_facts_gap_count")) not in {None, 0}

    needs_review = (
      _bool_from_row(sec_row.get("needs_human_review")) if sec_row else False
    ) or (
      _bool_from_row(fact_row.get("needs_human_review")) if fact_row else False
    ) or (
      _bool_from_row(bind_row.get("needs_human_review")) if bind_row else True
    )

    warning = None
    if needs_ocr and not vision_ocr_extracted:
      warning = "needs_ocr — 画像PDFの可能性（Google Vision OCR対象）"
    elif vision_ocr_extracted and sections_stale:
      warning = "OCR本文あり — OCR由来のセクション再抽出が必要"
    elif sections_extracted and not has_examples:
      warning = "examples未検出 — embodiments fallback候補を確認"

    target_count, target_types, fallback_used = _target_section_info_for_pub(sections_csv, norm)

    status = Top5PdfPipelineStatus(
      case_id=case_id,
      publication_number=norm,
      title=m.get("title", ""),
      assignee=m.get("assignee", m.get("organization", "")),
      google_patents_url=build_google_patents_url(norm),
      pdf_uploaded=uploaded,
      pdf_path=str(pdf_path) if pdf_path.exists() else None,
      pdf_text_extracted=text_extracted,
      text_length=_int_or_none(pdf_row.get("total_text_length")) if pdf_row else None,
      needs_ocr=needs_ocr,
      vision_ocr_available=ocr_available,
      vision_ocr_text_extracted=bool(vision_ocr_extracted),
      vision_ocr_extracted_pages=vision_ocr_pages,
      vision_ocr_total_text_length=vision_ocr_len,
      vision_ocr_status=ocr_status or None,
      text_extraction_method=text_method,
      sections_extracted=sections_extracted,
      sections_from_ocr=sections_from_ocr,
      sections_stale_vs_ocr=sections_stale,
      section_count=_int_or_none(sec_row.get("section_count")) if sec_row else None,
      examples_count=examples_count,
      comparative_examples_count=_int_or_none(sec_row.get("comparative_examples_count")) if sec_row else None,
      tables_count=_int_or_none(sec_row.get("tables_count")) if sec_row else None,
      has_examples=has_examples,
      target_sections_count=target_count,
      target_section_types=target_types,
      fallback_used=fallback_used,
      example_facts_extracted=bool(facts_extracted),
      fact_count=fact_count,
      property_fact_count=_int_or_none(fact_row.get("property_fact_count")) if fact_row else None,
      process_condition_fact_count=_int_or_none(fact_row.get("process_condition_fact_count")) if fact_row else None,
      structure_property_fact_count=_int_or_none(fact_row.get("structure_property_fact_count")) if fact_row else None,
      table_candidate_count=_int_or_none(fact_row.get("table_candidate_count")) if fact_row else None,
      unknown_fact_count=_int_or_none(fact_row.get("unknown_fact_count")) if fact_row else None,
      matched_user_keyword_count=_int_or_none(fact_row.get("matched_user_keyword_count")) if fact_row else None,
      claim_example_links_generated=bool(links_generated),
      linked_claim_count=_int_or_none(bind_row.get("linked_claim_count")) if bind_row else None,
      unlinked_claim_count=_int_or_none(bind_row.get("unlinked_claim_count")) if bind_row else None,
      evidence_aware_gaps_generated=evidence_gaps_generated,
      evidence_ready_for_review=bool(evidence_ready),
      evidence_no_example_facts=bool(evidence_no_facts),
      needs_human_review=needs_review,
      warning=warning,
    )
    status.pipeline_status_label, status.pipeline_status_details = infer_pipeline_status_label(status)
    status.next_action = infer_next_action(status)
    statuses.append(status)
  return statuses
