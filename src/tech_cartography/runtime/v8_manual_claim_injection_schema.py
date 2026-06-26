"""v8 Manual Claim Injection schema (Phase 27K)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tech_cartography.runtime.v8_sources_schema import utc_now_iso

MANUAL_CLAIM_SAFETY_NOTICES: tuple[str, ...] = (
  "claim 本文はユーザーが一次情報からコピーしたもののみを入力してください。",
  "システムは claim 本文を生成しません。",
  "Claim Map は技術整理であり、権利範囲解釈・FTO・侵害・有効性判断ではありません。",
  "Evidence Map は supporting evidence candidate であり proof ではありません。",
  "manually_verified / human_verified は自動付与しません。",
  "本 Phase ではメール送信・Scheduler 起動を行いません。",
)

VALID_CLAIM_SOURCE_TYPES: tuple[str, ...] = (
  "manual",
  "csv",
  "uploaded_pdf",
  "google_patents_user_copy",
  "bigquery_user_copy",
  "other_user_provided",
)

VALID_INJECTION_STATUSES: tuple[str, ...] = (
  "manual_input",
  "loaded",
  "rejected_empty",
  "rejected_too_short",
  "rejected_placeholder",
  "rejected_invalid_target",
)

REFRESH_NEXT_PHASES: tuple[str, ...] = (
  "Phase27L — Evidence Map / Gap Demo Polish",
  "Phase27M — UI最終調整",
  "Phase27N — Cloud Run v8反映準備",
)


@dataclass
class V8ManualClaimInjectionRequest:
  request_id: str
  case_id: str
  publication_number: str
  patent_title: str = ""
  claim_no: str = "1"
  claim_text: str = ""
  claim_source_type: str = "manual"
  claim_source_url: str = ""
  claim_source_path: str = ""
  user_note: str = ""
  created_at: str = field(default_factory=utc_now_iso)
  human_review_required: bool = True
  candidate_information_only: bool = True
  no_legal_judgement: bool = True

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class V8ManualClaimInjectionResult:
  result_id: str
  case_id: str
  publication_number: str
  claim_no: str
  claim_text_status: str
  normalized_claim_text: str = ""
  claim_text_length: int = 0
  saved_to_claims_input_csv: bool = False
  updated_claims_input_path: str = ""
  backup_path: str = ""
  warnings: list[str] = field(default_factory=list)
  next_refresh_steps: list[str] = field(default_factory=list)
  human_review_required: bool = True
  candidate_information_only: bool = True
  no_legal_judgement: bool = True
  created_at: str = field(default_factory=utc_now_iso)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class V8ManualClaimRefreshReport:
  report_id: str
  case_id: str
  publication_number: str
  generated_at: str
  claim_injection_result: V8ManualClaimInjectionResult | None = None
  claim_map_summary: str = ""
  evidence_map_summary: str = ""
  gap_next_actions_summary: str = ""
  fixed_point_observation_summary: str = ""
  validation_readiness_before: str = ""
  validation_readiness_after: str = ""
  claim_text_required_count_before: int = 0
  claim_text_required_count_after: int = 0
  artifact_paths: list[str] = field(default_factory=list)
  remaining_blocking_issues: list[str] = field(default_factory=list)
  next_human_actions: list[str] = field(default_factory=list)
  candidate_information_only: bool = True
  human_review_required: bool = True
  no_legal_judgement: bool = True
  no_email_send: bool = True
  no_scheduler_start: bool = True
  warnings: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return {
      "report_id": self.report_id,
      "case_id": self.case_id,
      "publication_number": self.publication_number,
      "generated_at": self.generated_at,
      "claim_injection_result": (
        self.claim_injection_result.to_dict() if self.claim_injection_result else None
      ),
      "claim_map_summary": self.claim_map_summary,
      "evidence_map_summary": self.evidence_map_summary,
      "gap_next_actions_summary": self.gap_next_actions_summary,
      "fixed_point_observation_summary": self.fixed_point_observation_summary,
      "validation_readiness_before": self.validation_readiness_before,
      "validation_readiness_after": self.validation_readiness_after,
      "claim_text_required_count_before": self.claim_text_required_count_before,
      "claim_text_required_count_after": self.claim_text_required_count_after,
      "artifact_paths": self.artifact_paths,
      "remaining_blocking_issues": self.remaining_blocking_issues,
      "next_human_actions": self.next_human_actions,
      "candidate_information_only": self.candidate_information_only,
      "human_review_required": self.human_review_required,
      "no_legal_judgement": self.no_legal_judgement,
      "no_email_send": self.no_email_send,
      "no_scheduler_start": self.no_scheduler_start,
      "warnings": self.warnings,
    }


@dataclass
class V8ManualClaimRefreshExport:
  export_id: str
  output_dir: str
  json_path: str
  md_path: str
  manifest_path: str
  artifact_trace_path: str
  created_at: str
  excel_warning: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)
