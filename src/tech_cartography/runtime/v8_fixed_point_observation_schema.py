"""v8 Fixed Point Observation schema (Phase 27H)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tech_cartography.runtime.v8_sources_schema import utc_now_iso

OBSERVATION_LOOP_SAFETY_NOTICES: tuple[str, ...] = (
  "定点観測ループは計画・提案・プレビューであり、Watch Profile を自動反映しません。",
  "メール送信と Scheduler は必須機能ですが、本 Phase では送信・起動しません。",
  "human review required — Watch Profile 更新は人手承認後に行います。",
  "candidate information only — Web/company 由来は候補扱いです。",
  "FTO、侵害、有効性判断、法的結論は行いません。",
  "approved / verified は自動付与しません。",
)

OBSERVATION_LOOP_NEXT_PHASES: tuple[str, ...] = (
  "3案件検証 — ローカル end-to-end checklist",
  "claim 本文投入 — claims_input.csv を人手更新後に再生成",
  "Cloud 反映前 — 最終ローカル確認（Cloud Build は節目のみ）",
)


@dataclass
class V8ObservationCycleInput:
  cycle_id: str
  case_id: str
  publication_number: str
  generated_at: str
  source_gap_next_actions_paths: list[str] = field(default_factory=list)
  source_evidence_map_paths: list[str] = field(default_factory=list)
  source_claim_map_paths: list[str] = field(default_factory=list)
  source_patent_shortlist_paths: list[str] = field(default_factory=list)
  source_sources_paths: list[str] = field(default_factory=list)
  current_gap_count: int = 0
  current_top_actions: list[str] = field(default_factory=list)
  current_watch_profile_update_proposal: str = ""
  current_digest_summary: str = ""
  candidate_information_only: bool = True
  human_review_required: bool = True
  no_legal_judgement: bool = True

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class V8WatchProfileUpdateProposal:
  proposal_id: str
  case_id: str
  proposal_type: str
  proposed_items: list[str] = field(default_factory=list)
  reason: str = ""
  source_gap_ids: list[str] = field(default_factory=list)
  source_action_ids: list[str] = field(default_factory=list)
  affected_claim_axes: list[str] = field(default_factory=list)
  priority_label: str = "medium"
  review_status: str = "pending_human_review"
  human_review_required: bool = True
  candidate_information_only: bool = True
  no_legal_judgement: bool = True
  caution_flags: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> V8WatchProfileUpdateProposal:
    known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    filtered = {key: data[key] for key in known if key in data}
    for list_key in (
      "proposed_items",
      "source_gap_ids",
      "source_action_ids",
      "affected_claim_axes",
      "caution_flags",
    ):
      if list_key not in filtered:
        filtered[list_key] = []
    return cls(**filtered)


@dataclass
class V8SchedulerFollowupPlan:
  scheduler_plan_id: str
  case_id: str
  schedule_mode: str = "dry_run_only"
  planned_cycle_label: str = "next_manual_cycle"
  planned_steps: list[str] = field(default_factory=list)
  blocked_steps: list[str] = field(default_factory=list)
  required_human_inputs: list[str] = field(default_factory=list)
  scheduler_followup_hint: str = ""
  scheduler_enabled: bool = False
  no_scheduler_start: bool = True
  caution_flags: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> V8SchedulerFollowupPlan:
    known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    filtered = {key: data[key] for key in known if key in data}
    for list_key in ("planned_steps", "blocked_steps", "required_human_inputs", "caution_flags"):
      if list_key not in filtered:
        filtered[list_key] = []
    return cls(**filtered)


@dataclass
class V8EmailDigestPlan:
  digest_plan_id: str
  case_id: str
  digest_mode: str = "preview_only"
  subject_draft: str = ""
  digest_summary: str = ""
  top_3_actions_summary: str = ""
  watch_profile_update_summary: str = ""
  evidence_gap_change_summary: str = ""
  recipient_group_label: str = "approved_members"
  email_digest_hint: str = ""
  email_send_enabled: bool = False
  no_email_send: bool = True
  caution_flags: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> V8EmailDigestPlan:
    known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    filtered = {key: data[key] for key in known if key in data}
    if "caution_flags" not in filtered:
      filtered["caution_flags"] = []
    return cls(**filtered)


@dataclass
class V8ObservationLoopReport:
  report_id: str
  case_id: str
  publication_number: str
  generated_at: str
  loop_status: str = "ready_for_human_review"
  current_state_summary: str = ""
  what_changed_or_needs_change: str = ""
  watch_profile_update_proposals: list[V8WatchProfileUpdateProposal] = field(default_factory=list)
  scheduler_followup_plan: V8SchedulerFollowupPlan | None = None
  email_digest_plan: V8EmailDigestPlan | None = None
  top_3_next_cycle_tasks: list[str] = field(default_factory=list)
  artifact_trace: list[str] = field(default_factory=list)
  source_artifact_paths: list[str] = field(default_factory=list)
  export_paths: list[str] = field(default_factory=list)
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
      "loop_status": self.loop_status,
      "current_state_summary": self.current_state_summary,
      "what_changed_or_needs_change": self.what_changed_or_needs_change,
      "watch_profile_update_proposals": [p.to_dict() for p in self.watch_profile_update_proposals],
      "scheduler_followup_plan": (
        self.scheduler_followup_plan.to_dict() if self.scheduler_followup_plan else None
      ),
      "email_digest_plan": self.email_digest_plan.to_dict() if self.email_digest_plan else None,
      "top_3_next_cycle_tasks": self.top_3_next_cycle_tasks,
      "artifact_trace": self.artifact_trace,
      "source_artifact_paths": self.source_artifact_paths,
      "export_paths": self.export_paths,
      "candidate_information_only": self.candidate_information_only,
      "human_review_required": self.human_review_required,
      "no_legal_judgement": self.no_legal_judgement,
      "no_email_send": self.no_email_send,
      "no_scheduler_start": self.no_scheduler_start,
      "warnings": self.warnings,
    }


@dataclass
class V8ObservationLoopExport:
  export_id: str
  case_id: str
  publication_number: str
  output_dir: str
  json_path: str
  md_path: str
  xlsx_path: str
  manifest_path: str
  watch_profile_proposal_path: str
  scheduler_plan_path: str
  email_digest_plan_path: str
  created_at: str
  excel_warning: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)
