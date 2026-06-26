"""v8 Three Case Validation schema (Phase 27I)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tech_cartography.runtime.v8_sources_schema import utc_now_iso

VALIDATION_SAFETY_NOTICES: tuple[str, ...] = (
  "ready はデモ説明可能という意味であり、技術的正しさ・特許的有効性を意味しません。",
  "Evidence Map は supporting evidence candidate であり proof ではありません。",
  "Gap は未確認事項であり、特許の弱点・無効性・侵害可能性ではありません。",
  "FTO、侵害、有効性判断、法的結論は行いません。",
  "candidate information only — Web/company 由来は候補扱いです。",
  "本 Phase ではメール送信・Scheduler 起動を行いません（計画のみ確認）。",
)

VALIDATION_NEXT_PHASES: tuple[str, ...] = (
  "Phase27J — claim 本文を数件投入して Evidence Map の見栄え改善",
  "Phase27K — UI 最終調整",
  "Phase27L — Cloud Run v8 反映準備",
)

VALIDATION_STEP_IDS: tuple[str, ...] = (
  "sources",
  "patent_shortlist",
  "claim_map",
  "evidence_map",
  "gap_next_actions",
  "fixed_point_observation",
  "export",
)


@dataclass
class V8CaseValidationStepResult:
  step_id: str
  case_id: str
  step_name: str
  status: str = "skipped"
  summary: str = ""
  required_output_exists: bool = False
  artifact_paths: list[str] = field(default_factory=list)
  key_counts: dict[str, int] = field(default_factory=dict)
  warnings: list[str] = field(default_factory=list)
  blocking_issues: list[str] = field(default_factory=list)
  next_fix_hint: str = ""
  candidate_information_only: bool = True
  human_review_required: bool = True
  no_legal_judgement: bool = True
  created_at: str = field(default_factory=utc_now_iso)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class V8CaseValidationReport:
  report_id: str
  case_id: str
  case_name: str
  generated_at: str
  overall_status: str = "warning"
  step_results: list[V8CaseValidationStepResult] = field(default_factory=list)
  source_count: int = 0
  patent_shortlist_count: int = 0
  claim_map_count: int = 0
  evidence_link_count: int = 0
  gap_count: int = 0
  next_action_count: int = 0
  fixed_point_loop_status: str = ""
  export_artifact_count: int = 0
  top_findings: list[str] = field(default_factory=list)
  known_limitations: list[str] = field(default_factory=list)
  next_human_actions: list[str] = field(default_factory=list)
  artifact_trace: list[str] = field(default_factory=list)
  readiness_for_demo: str = "not_ready"
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
      "case_name": self.case_name,
      "generated_at": self.generated_at,
      "overall_status": self.overall_status,
      "step_results": [s.to_dict() for s in self.step_results],
      "source_count": self.source_count,
      "patent_shortlist_count": self.patent_shortlist_count,
      "claim_map_count": self.claim_map_count,
      "evidence_link_count": self.evidence_link_count,
      "gap_count": self.gap_count,
      "next_action_count": self.next_action_count,
      "fixed_point_loop_status": self.fixed_point_loop_status,
      "export_artifact_count": self.export_artifact_count,
      "top_findings": self.top_findings,
      "known_limitations": self.known_limitations,
      "next_human_actions": self.next_human_actions,
      "artifact_trace": self.artifact_trace,
      "readiness_for_demo": self.readiness_for_demo,
      "candidate_information_only": self.candidate_information_only,
      "human_review_required": self.human_review_required,
      "no_legal_judgement": self.no_legal_judgement,
      "no_email_send": self.no_email_send,
      "no_scheduler_start": self.no_scheduler_start,
      "warnings": self.warnings,
    }


@dataclass
class V8ThreeCaseValidationPack:
  pack_id: str
  generated_at: str
  cases: list[V8CaseValidationReport] = field(default_factory=list)
  overall_status: str = "warning"
  total_cases: int = 3
  ready_case_count: int = 0
  warning_case_count: int = 0
  fail_case_count: int = 0
  cross_case_summary: str = ""
  common_blocking_issues: list[str] = field(default_factory=list)
  common_next_actions: list[str] = field(default_factory=list)
  demo_readiness_summary: str = ""
  cloud_readiness_summary: str = ""
  safety_notice: str = ""
  artifact_paths: list[str] = field(default_factory=list)
  no_legal_judgement: bool = True
  no_email_send: bool = True
  no_scheduler_start: bool = True

  def to_dict(self) -> dict[str, Any]:
    return {
      "pack_id": self.pack_id,
      "generated_at": self.generated_at,
      "cases": [c.to_dict() for c in self.cases],
      "overall_status": self.overall_status,
      "total_cases": self.total_cases,
      "ready_case_count": self.ready_case_count,
      "warning_case_count": self.warning_case_count,
      "fail_case_count": self.fail_case_count,
      "cross_case_summary": self.cross_case_summary,
      "common_blocking_issues": self.common_blocking_issues,
      "common_next_actions": self.common_next_actions,
      "demo_readiness_summary": self.demo_readiness_summary,
      "cloud_readiness_summary": self.cloud_readiness_summary,
      "safety_notice": self.safety_notice,
      "artifact_paths": self.artifact_paths,
      "no_legal_judgement": self.no_legal_judgement,
      "no_email_send": self.no_email_send,
      "no_scheduler_start": self.no_scheduler_start,
    }


@dataclass
class V8ThreeCaseValidationExport:
  export_id: str
  output_dir: str
  json_path: str
  md_path: str
  xlsx_path: str
  manifest_path: str
  demo_readiness_path: str
  cloud_readiness_path: str
  case_report_paths: dict[str, str]
  created_at: str
  excel_warning: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)
