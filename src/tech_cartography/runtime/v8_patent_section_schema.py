"""Patent fulltext section schema (Phase 27S.2)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SECTION_EXTRACTION_NOTICES: tuple[str, ...] = (
  "セクション判定は候補であり確定ではありません — needs_human_review を確認してください。",
  "このPhaseではルールベース分割のみ — Gemini / OpenAI / OCRは使用しません。",
  "実施例条件・物性値の構造化は次Phase27S.3で行います。",
  "Evidenceは証明ではなく裏取り候補、Gapは弱点ではなく未確認事項です。",
)

VALID_SECTION_TYPES: tuple[str, ...] = (
  "claims",
  "description",
  "technical_field",
  "background",
  "summary",
  "embodiments",
  "examples",
  "comparative_examples",
  "tables",
  "drawings",
  "unknown",
)

VALID_SECTION_STATUSES: tuple[str, ...] = (
  "ok",
  "needs_review",
  "no_headings",
  "empty_input",
  "error",
)


@dataclass
class PatentFulltextSection:
  case_id: str
  publication_number: str
  section_id: str
  section_type: str
  section_title: str | None
  section_text: str
  page_start: int | None
  page_end: int | None
  text_length: int
  confidence: float
  needs_human_review: bool
  detection_method: str
  warning: str | None = None

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class PatentSectionExtractionResult:
  case_id: str
  publication_number: str
  source_raw_csv: str | None = None
  section_count: int = 0
  examples_count: int = 0
  comparative_examples_count: int = 0
  tables_count: int = 0
  has_claims: bool = False
  has_description: bool = False
  has_examples: bool = False
  needs_human_review: bool = False
  sections: list[PatentFulltextSection] = field(default_factory=list)
  output_dir: str | None = None
  status: str = "ok"
  warning: str | None = None

  def to_dict(self) -> dict[str, Any]:
    return {
      "case_id": self.case_id,
      "publication_number": self.publication_number,
      "source_raw_csv": self.source_raw_csv,
      "section_count": self.section_count,
      "examples_count": self.examples_count,
      "comparative_examples_count": self.comparative_examples_count,
      "tables_count": self.tables_count,
      "has_claims": self.has_claims,
      "has_description": self.has_description,
      "has_examples": self.has_examples,
      "needs_human_review": self.needs_human_review,
      "sections": [s.to_dict() for s in self.sections],
      "output_dir": self.output_dir,
      "status": self.status,
      "warning": self.warning,
    }
