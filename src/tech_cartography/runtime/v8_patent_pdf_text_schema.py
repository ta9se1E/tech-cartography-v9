"""Patent PDF text extraction schema (Phase 27S.1)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

PDF_TEXT_EXTRACTION_NOTICES: tuple[str, ...] = (
  "このPhaseではPDF本文の抽出のみ — OCR / Gemini / OpenAI / 実施例ファクト抽出は行いません。",
  "抽出結果は原典確認の補助であり、Evidenceは証明ではなく裏取り候補です。",
  "Gapは弱点ではなく未確認事項です。FTO、侵害、有効性判断は行いません。",
  "Google PatentsからのPDF自動取得・スクレイピングは行いません。",
)

VALID_EXTRACTION_STATUSES: tuple[str, ...] = (
  "ok",
  "needs_ocr",
  "empty",
  "error",
  "library_missing",
  "file_missing",
)


@dataclass
class PatentPdfTextPage:
  case_id: str
  publication_number: str
  source_file: str
  page_no: int
  text: str
  text_length: int
  extraction_method: str
  needs_ocr: bool
  warning: str | None = None

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class PatentPdfTextExtractionResult:
  case_id: str
  publication_number: str
  source_file: str
  page_count: int = 0
  total_text_length: int = 0
  extracted_pages: int = 0
  needs_ocr: bool = False
  extraction_method: str = "pypdf"
  pages: list[PatentPdfTextPage] = field(default_factory=list)
  output_dir: str | None = None
  status: str = "ok"
  warning: str | None = None

  def to_dict(self) -> dict[str, Any]:
    return {
      "case_id": self.case_id,
      "publication_number": self.publication_number,
      "source_file": self.source_file,
      "page_count": self.page_count,
      "total_text_length": self.total_text_length,
      "extracted_pages": self.extracted_pages,
      "needs_ocr": self.needs_ocr,
      "extraction_method": self.extraction_method,
      "pages": [p.to_dict() for p in self.pages],
      "output_dir": self.output_dir,
      "status": self.status,
      "warning": self.warning,
    }
