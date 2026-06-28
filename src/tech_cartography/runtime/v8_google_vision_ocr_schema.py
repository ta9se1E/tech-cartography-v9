"""Google Vision OCR schema (Phase 27S.5)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

GOOGLE_VISION_OCR_NOTICES: tuple[str, ...] = (
  "OCR結果は自動抽出テキストであり、誤読の可能性があります — 確定本文ではありません。",
  "実施例・数値・単位は必ず原文PDFで人手確認してください。",
  "OCRは明示ボタン操作時のみ実行します — 自動実行しません。",
  "Evidenceは証明ではなく裏取り候補、Gapは弱点ではなく未確認事項です。",
)

EXTRACTION_METHOD_VISION = "google_vision_ocr"
OCR_HUMAN_REVIEW_WARNING = "OCR text requires human review"

VALID_OCR_STATUSES: tuple[str, ...] = (
  "disabled",
  "bucket_missing",
  "dependency_missing",
  "auth_error",
  "upload_failed",
  "ocr_started",
  "ocr_completed",
  "ocr_failed",
  "parse_failed",
  "success",
)


@dataclass
class GoogleVisionOcrPage:
  case_id: str
  publication_number: str
  page_no: int
  text: str
  text_length: int
  confidence: float | None = None
  extraction_method: str = EXTRACTION_METHOD_VISION
  needs_human_review: bool = True
  warning: str | None = OCR_HUMAN_REVIEW_WARNING

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class GoogleVisionOcrResult:
  case_id: str
  publication_number: str
  source_pdf_path: str
  gcs_input_uri: str | None = None
  gcs_output_uri: str | None = None
  page_count: int | None = None
  extracted_pages: int = 0
  total_text_length: int = 0
  needs_human_review: bool = True
  status: str = "disabled"
  warning: str | None = None
  output_dir: str | None = None
  pages: list[GoogleVisionOcrPage] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    d = asdict(self)
    d["pages"] = [p.to_dict() for p in self.pages]
    return d
