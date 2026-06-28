"""Top5 PDF pipeline status schema (Phase 27S.4.1)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

TOP5_PDF_PIPELINE_NOTICES: tuple[str, ...] = (
  "PDF解析は候補データの確認用です — Evidenceは証明ではなく裏取り候補です。",
  "Gapは弱点ではなく未確認事項です。",
  "Geminiは明示ボタン操作時のみ実行します。",
  "Google Vision OCRも明示ボタン操作時のみ実行します。",
)


@dataclass
class Top5PdfPipelineStatus:
  case_id: str
  publication_number: str
  title: str = ""
  assignee: str = ""
  google_patents_url: str = ""
  pdf_uploaded: bool = False
  pdf_path: str | None = None
  pdf_text_extracted: bool = False
  text_length: int | None = None
  needs_ocr: bool = False
  vision_ocr_available: bool = False
  vision_ocr_text_extracted: bool = False
  vision_ocr_extracted_pages: int | None = None
  vision_ocr_total_text_length: int | None = None
  vision_ocr_status: str | None = None
  text_extraction_method: str | None = None
  sections_extracted: bool = False
  sections_from_ocr: bool = False
  sections_stale_vs_ocr: bool = False
  section_count: int | None = None
  examples_count: int | None = None
  comparative_examples_count: int | None = None
  tables_count: int | None = None
  has_examples: bool = False
  target_sections_count: int | None = None
  target_section_types: str = ""
  fallback_used: bool = False
  example_facts_extracted: bool = False
  fact_count: int | None = None
  property_fact_count: int | None = None
  process_condition_fact_count: int | None = None
  structure_property_fact_count: int | None = None
  table_candidate_count: int | None = None
  unknown_fact_count: int | None = None
  matched_user_keyword_count: int | None = None
  claim_example_links_generated: bool = False
  linked_claim_count: int | None = None
  unlinked_claim_count: int | None = None
  evidence_aware_gaps_generated: bool = False
  evidence_ready_for_review: bool = False
  evidence_no_example_facts: bool = False
  pipeline_status_label: str = ""
  pipeline_status_details: str = ""
  next_action: str = ""
  warning: str | None = None
  needs_human_review: bool = True

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)
