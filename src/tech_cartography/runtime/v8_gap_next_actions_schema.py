"""v8 Gap / Next Actions schema (Phase 27G)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tech_cartography.runtime.v8_sources_schema import utc_now_iso

GAP_NEXT_ACTIONS_SAFETY_NOTICES: tuple[str, ...] = (
  "Gap は未確認事項であり、特許の弱点・無効性・侵害可能性を意味しません。",
  "Next Action は人間が次に確認する技術調査タスクであり、法的判断ではありません。",
  "Gap is not invalidity / weakness / infringement conclusion。",
  "FTO、侵害、有効性判断、法的結論は行いません。",
  "candidate information only — Web/company 由来は候補扱いです。",
  "manually_verified / human_verified は自動付与しません。",
)

GAP_NEXT_PHASES: tuple[str, ...] = (
  "定点観測 — 次回 Scheduler で Gap 再確認",
  "Watch Profile — update proposal を人手承認後に反映",
  "メール Digest — Evidence Gap 変化を次回サイクルで追跡（本 Phase では送信しない）",
)


@dataclass
class V8EvidenceGapRecord:
  gap_id: str
  case_id: str
  publication_number: str
  patent_title: str
  claim_id: str
  claim_no: str
  primary_axis: str
  technical_axis_labels: list[str] = field(default_factory=list)
  gap_type: str = "unknown"
  gap_title: str = ""
  gap_description: str = ""
  why_it_matters: str = ""
  source_evidence_links: list[str] = field(default_factory=list)
  related_source_ids: list[str] = field(default_factory=list)
  related_source_titles: list[str] = field(default_factory=list)
  related_evidence_needed: list[str] = field(default_factory=list)
  severity_label: str = "unknown"
  urgency_label: str = "unknown"
  confidence_label: str = "medium"
  human_review_required: bool = True
  candidate_information_only: bool = False
  no_legal_judgement: bool = True
  caution_flags: list[str] = field(default_factory=list)
  next_action_id: str = ""
  created_at: str = field(default_factory=utc_now_iso)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> V8EvidenceGapRecord:
    known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    filtered = {key: data[key] for key in known if key in data}
    for list_key in (
      "technical_axis_labels",
      "source_evidence_links",
      "related_source_ids",
      "related_source_titles",
      "related_evidence_needed",
      "caution_flags",
    ):
      if list_key not in filtered:
        filtered[list_key] = []
    return cls(**filtered)


@dataclass
class V8NextVerificationAction:
  action_id: str
  case_id: str
  action_rank: int
  action_type: str
  action_title: str
  action_description: str = ""
  target_publication_number: str = ""
  target_claim_no: str = ""
  target_source_id: str = ""
  target_source_title: str = ""
  target_url: str = ""
  expected_output: str = ""
  estimated_effort_label: str = "unknown"
  priority_reason: str = ""
  owner_suggestion: str = "researcher"
  next_step_command_hint: str = ""
  watch_profile_update_hint: str = ""
  scheduler_followup_hint: str = ""
  email_digest_hint: str = ""
  caution_flags: list[str] = field(default_factory=list)
  candidate_information_only: bool = False
  human_review_required: bool = True
  no_legal_judgement: bool = True
  created_at: str = field(default_factory=utc_now_iso)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> V8NextVerificationAction:
    known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    filtered = {key: data[key] for key in known if key in data}
    if "caution_flags" not in filtered:
      filtered["caution_flags"] = []
    return cls(**filtered)


@dataclass
class V8GapNextActionsReport:
  report_id: str
  case_id: str
  publication_number: str
  generated_at: str
  gaps: list[V8EvidenceGapRecord] = field(default_factory=list)
  next_actions: list[V8NextVerificationAction] = field(default_factory=list)
  top_3_actions: list[V8NextVerificationAction] = field(default_factory=list)
  gap_count: int = 0
  action_count: int = 0
  count_by_gap_type: dict[str, int] = field(default_factory=dict)
  count_by_action_type: dict[str, int] = field(default_factory=dict)
  count_by_urgency: dict[str, int] = field(default_factory=dict)
  source_artifact_paths: list[str] = field(default_factory=list)
  evidence_map_artifact_paths: list[str] = field(default_factory=list)
  watch_profile_update_proposal: str = ""
  digest_summary: str = ""
  warnings: list[str] = field(default_factory=list)
  candidate_information_only: bool = True
  human_review_required: bool = True
  no_legal_judgement: bool = True

  def to_dict(self) -> dict[str, Any]:
    return {
      "report_id": self.report_id,
      "case_id": self.case_id,
      "publication_number": self.publication_number,
      "generated_at": self.generated_at,
      "gaps": [g.to_dict() for g in self.gaps],
      "next_actions": [a.to_dict() for a in self.next_actions],
      "top_3_actions": [a.to_dict() for a in self.top_3_actions],
      "gap_count": self.gap_count,
      "action_count": self.action_count,
      "count_by_gap_type": self.count_by_gap_type,
      "count_by_action_type": self.count_by_action_type,
      "count_by_urgency": self.count_by_urgency,
      "source_artifact_paths": self.source_artifact_paths,
      "evidence_map_artifact_paths": self.evidence_map_artifact_paths,
      "watch_profile_update_proposal": self.watch_profile_update_proposal,
      "digest_summary": self.digest_summary,
      "warnings": self.warnings,
      "candidate_information_only": self.candidate_information_only,
      "human_review_required": self.human_review_required,
      "no_legal_judgement": self.no_legal_judgement,
    }


@dataclass
class V8GapNextActionsExport:
  export_id: str
  case_id: str
  publication_number: str
  output_dir: str
  csv_path: str
  md_path: str
  xlsx_path: str
  manifest_path: str
  watch_profile_proposal_path: str
  digest_summary_path: str
  created_at: str
  excel_warning: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)
