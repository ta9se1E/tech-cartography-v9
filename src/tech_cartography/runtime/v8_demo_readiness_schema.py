"""v8 Demo Readiness schema (Phase 27M)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tech_cartography.runtime.v8_sources_schema import utc_now_iso

DEMO_READINESS_SAFETY_NOTICES: tuple[str, ...] = (
  "artifact missing と true zero（実際に0件）は区別して表示します。",
  "artifact 未生成の件数0は ready 扱いにしません。",
  "Evidence Map is not proof — supporting evidence candidate のみ。",
  "Gap is not invalidity / weakness — 未確認事項です。",
  "FTO、侵害、有効性判断、法的結論は行いません。",
  "本 Phase では Cloud Build / Cloud Run deploy / メール送信 / Scheduler 起動を行いません。",
)

DEMO_READINESS_NEXT_PHASES: tuple[str, ...] = (
  "Phase27N — Cloud Run v8反映準備",
  "Phase27O — Cloud Run v8反映",
  "Phase27P — 提出用README / スクショ / 動画準備",
)

DEMO_STEP_NAMES: tuple[str, ...] = (
  "input",
  "sources",
  "large_candidate_import",
  "large_candidate_shortlist",
  "ranking_explanation",
  "claim_map",
  "manual_claim_injection",
  "evidence_map",
  "gap_next_actions",
  "fixed_point_observation",
  "demo_polish_pack",
  "export",
)

STEP_STATUS_VALUES: tuple[str, ...] = (
  "ready",
  "warning",
  "missing",
  "not_generated",
  "needs_previous_step",
  "skipped",
)


@dataclass
class V8DemoStepStatus:
  step_id: str
  case_id: str
  step_name: str
  status: str
  display_label: str = ""
  summary: str = ""
  artifact_paths: list[str] = field(default_factory=list)
  primary_artifact_exists: bool = False
  key_counts: dict[str, str | int] = field(default_factory=dict)
  next_user_action: str = ""
  next_tab: str = ""
  next_button_hint: str = ""
  warnings: list[str] = field(default_factory=list)
  blocking_issues: list[str] = field(default_factory=list)
  candidate_information_only: bool = True
  no_legal_judgement: bool = True
  created_at: str = field(default_factory=utc_now_iso)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class V8CaseDemoReadiness:
  case_id: str
  case_name: str
  generated_at: str
  overall_status: str = "not_ready"
  current_recommended_step: str = ""
  completed_step_count: int = 0
  total_step_count: int = 0
  step_statuses: list[V8DemoStepStatus] = field(default_factory=list)
  large_candidate_count: int | None = None
  top100_count: int | None = None
  top20_count: int | None = None
  top5_count: int | None = None
  manual_claim_count: int | None = None
  claim_text_required_count: int | None = None
  evidence_link_count: int | None = None
  gap_count: int | None = None
  demo_polish_pack_exists: bool = False
  export_pack_exists: bool = False
  recommended_demo_flow: list[str] = field(default_factory=list)
  next_3_user_actions: list[str] = field(default_factory=list)
  caveats: list[str] = field(default_factory=list)
  artifact_trace: list[str] = field(default_factory=list)
  no_email_send: bool = True
  no_scheduler_start: bool = True
  no_legal_judgement: bool = True
  warnings: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return {
      "case_id": self.case_id,
      "case_name": self.case_name,
      "generated_at": self.generated_at,
      "overall_status": self.overall_status,
      "current_recommended_step": self.current_recommended_step,
      "completed_step_count": self.completed_step_count,
      "total_step_count": self.total_step_count,
      "step_statuses": [s.to_dict() for s in self.step_statuses],
      "large_candidate_count": self.large_candidate_count,
      "top100_count": self.top100_count,
      "top20_count": self.top20_count,
      "top5_count": self.top5_count,
      "manual_claim_count": self.manual_claim_count,
      "claim_text_required_count": self.claim_text_required_count,
      "evidence_link_count": self.evidence_link_count,
      "gap_count": self.gap_count,
      "demo_polish_pack_exists": self.demo_polish_pack_exists,
      "export_pack_exists": self.export_pack_exists,
      "recommended_demo_flow": self.recommended_demo_flow,
      "next_3_user_actions": self.next_3_user_actions,
      "caveats": self.caveats,
      "artifact_trace": self.artifact_trace,
      "no_email_send": self.no_email_send,
      "no_scheduler_start": self.no_scheduler_start,
      "no_legal_judgement": self.no_legal_judgement,
      "warnings": self.warnings,
    }


@dataclass
class V8DemoReadinessReport:
  report_id: str
  generated_at: str
  cases: list[V8CaseDemoReadiness] = field(default_factory=list)
  overall_status: str = "not_ready"
  ready_case_count: int = 0
  warning_case_count: int = 0
  not_ready_case_count: int = 0
  common_next_actions: list[str] = field(default_factory=list)
  demo_operator_checklist: list[str] = field(default_factory=list)
  cloud_preparation_checklist: list[str] = field(default_factory=list)
  artifact_trace: list[str] = field(default_factory=list)
  no_cloud_build: bool = True
  no_cloud_run_deploy: bool = True
  no_email_send: bool = True
  no_scheduler_start: bool = True
  no_legal_judgement: bool = True
  warnings: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return {
      "report_id": self.report_id,
      "generated_at": self.generated_at,
      "cases": [c.to_dict() for c in self.cases],
      "overall_status": self.overall_status,
      "ready_case_count": self.ready_case_count,
      "warning_case_count": self.warning_case_count,
      "not_ready_case_count": self.not_ready_case_count,
      "common_next_actions": self.common_next_actions,
      "demo_operator_checklist": self.demo_operator_checklist,
      "cloud_preparation_checklist": self.cloud_preparation_checklist,
      "artifact_trace": self.artifact_trace,
      "no_cloud_build": self.no_cloud_build,
      "no_cloud_run_deploy": self.no_cloud_run_deploy,
      "no_email_send": self.no_email_send,
      "no_scheduler_start": self.no_scheduler_start,
      "no_legal_judgement": self.no_legal_judgement,
      "warnings": self.warnings,
    }


@dataclass
class V8DemoReadinessExport:
  export_id: str
  output_dir: str
  json_path: str
  md_path: str
  manifest_path: str
  operator_checklist_path: str
  cloud_checklist_path: str
  created_at: str

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)
