"""v8 Claim batch import schema (Phase 27Q.1)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tech_cartography.runtime.v8_sources_schema import utc_now_iso

CLAIM_BATCH_SAFETY_NOTICES: tuple[str, ...] = (
  "claim 本文はユーザー提供のみ — システムは自動生成しません。",
  "JP/CN 特許の claim 本文は BigQuery から取得しません — CSV/Excel または手動入力。",
  "FTO、侵害、有効性判断、法的結論は行いません。",
  "fake DOI / fake URL / placeholder claim は reject します。",
)

VALID_DUPLICATE_MODES: tuple[str, ...] = (
  "update",
  "skip",
  "append",
)

REQUIRED_COLUMNS: tuple[str, ...] = (
  "publication_number",
  "claim_no",
  "claim_text",
)

OPTIONAL_COLUMNS: tuple[str, ...] = (
  "claim_source_url",
  "claim_source_type",
  "user_note",
  "patent_title",
  "language",
  "source_file_name",
)

TEMPLATE_COLUMNS: tuple[str, ...] = (
  "publication_number",
  "claim_no",
  "claim_text",
  "claim_source_url",
  "claim_source_type",
  "user_note",
)


@dataclass
class ClaimBatchRow:
  row_number: int
  publication_number: str
  claim_no: str
  claim_text: str
  claim_source_url: str = ""
  claim_source_type: str = "manual"
  user_note: str = ""
  patent_title: str = ""
  language: str = ""
  source_file_name: str = ""
  status: str = "pending"
  reject_reason: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class ClaimBatchImportReport:
  report_id: str
  case_id: str
  input_file: str
  mode: str
  duplicate_mode: str
  total_rows: int
  valid_rows: int
  rejected_rows: int
  applied_rows: int
  skipped_rows: int
  updated_rows: int
  backup_path: str = ""
  updated_claims_input_path: str = ""
  warnings: list[str] = field(default_factory=list)
  rows: list[ClaimBatchRow] = field(default_factory=list)
  rejected: list[ClaimBatchRow] = field(default_factory=list)
  generated_at: str = field(default_factory=utc_now_iso)
  no_email_send: bool = True
  no_scheduler_start: bool = True

  def to_dict(self) -> dict[str, Any]:
    return {
      **asdict(self),
      "rows": [r.to_dict() for r in self.rows],
      "rejected": [r.to_dict() for r in self.rejected],
    }
