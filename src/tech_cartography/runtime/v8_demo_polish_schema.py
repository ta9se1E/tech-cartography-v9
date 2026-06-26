"""v8 Demo Polish schema (Phase 27L)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tech_cartography.runtime.v8_sources_schema import utc_now_iso

DEMO_POLISH_SAFETY_NOTICES: tuple[str, ...] = (
  "Evidence Map is not proof — supporting evidence candidate のみです。",
  "paper / web / company は裏付け候補であり、証明・確定 Evidence ではありません。",
  "Gap is not invalidity / weakness / infringement conclusion — 未確認事項です。",
  "claim 本文はユーザー提供のみ。システムは claim 本文を生成しません。",
  "実施例本文・論文本文を読んだことにはしません。",
  "FTO、侵害、有効性判断、法的結論は行いません。",
  "本 Phase ではメール送信・Scheduler 起動を行いません。",
)

DEMO_POLISH_NEXT_PHASES: tuple[str, ...] = (
  "Phase27M — UI最終調整",
  "Phase27N — Cloud Run v8反映準備",
  "Phase27O — Cloud Run v8反映",
)

VALID_CLAIM_TEXT_STATUSES: tuple[str, ...] = (
  "not_loaded",
  "manual_input",
  "loaded",
  "mixed",
  "unknown",
)

STORY_CARD_TYPES: tuple[str, ...] = (
  "population_to_top5",
  "claim_status",
  "evidence_candidates",
  "evidence_gaps",
  "next_actions",
  "observation_loop",
  "caveat",
)


@dataclass
class V8EvidenceDemoStatus:
  status_id: str
  case_id: str
  publication_number: str
  patent_title: str = ""
  claim_text_status: str = "unknown"
  claim_text_required_count: int = 0
  manual_claim_count: int = 0
  evidence_link_count: int = 0
  paper_candidate_count: int = 0
  web_candidate_count: int = 0
  company_candidate_count: int = 0
  patent_candidate_count: int = 0
  missing_evidence_count: int = 0
  needs_human_review_count: int = 0
  strongest_candidate_summary: str = ""
  weakest_point_summary: str = ""
  next_verification_summary: str = ""
  supporting_evidence_candidate_only: bool = True
  evidence_map_not_proof: bool = True
  no_legal_judgement: bool = True
  no_email_send: bool = True
  no_scheduler_start: bool = True
  warnings: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class V8GapDemoStatus:
  status_id: str
  case_id: str
  publication_number: str
  gap_count: int = 0
  top_gap_types: list[str] = field(default_factory=list)
  top_3_next_actions: list[str] = field(default_factory=list)
  claim_text_gap_count: int = 0
  example_support_gap_count: int = 0
  paper_support_gap_count: int = 0
  source_url_gap_count: int = 0
  web_company_only_gap_count: int = 0
  before_after_summary: str = ""
  next_human_action_summary: str = ""
  gap_is_not_invalidity: bool = True
  no_legal_judgement: bool = True
  warnings: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class V8DemoStoryCard:
  card_id: str
  case_id: str
  card_title: str
  card_subtitle: str = ""
  card_type: str = "caveat"
  key_message: str = ""
  supporting_metrics: dict[str, str | int] = field(default_factory=dict)
  action_hint: str = ""
  caution_text: str = ""
  display_priority: int = 99

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class V8DemoPolishReport:
  report_id: str
  case_id: str
  publication_number: str
  generated_at: str
  large_candidate_summary: str = ""
  patent_shortlist_summary: str = ""
  evidence_demo_status: V8EvidenceDemoStatus | None = None
  gap_demo_status: V8GapDemoStatus | None = None
  story_cards: list[V8DemoStoryCard] = field(default_factory=list)
  demo_narrative: str = ""
  before_after_claim_status: str = ""
  recommended_demo_steps: list[str] = field(default_factory=list)
  remaining_limitations: list[str] = field(default_factory=list)
  artifact_trace: list[str] = field(default_factory=list)
  export_paths: list[str] = field(default_factory=list)
  candidate_information_only: bool = True
  human_review_required: bool = True
  supporting_evidence_candidate_only: bool = True
  evidence_map_not_proof: bool = True
  gap_is_not_invalidity: bool = True
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
      "large_candidate_summary": self.large_candidate_summary,
      "patent_shortlist_summary": self.patent_shortlist_summary,
      "evidence_demo_status": (
        self.evidence_demo_status.to_dict() if self.evidence_demo_status else None
      ),
      "gap_demo_status": self.gap_demo_status.to_dict() if self.gap_demo_status else None,
      "story_cards": [c.to_dict() for c in self.story_cards],
      "demo_narrative": self.demo_narrative,
      "before_after_claim_status": self.before_after_claim_status,
      "recommended_demo_steps": self.recommended_demo_steps,
      "remaining_limitations": self.remaining_limitations,
      "artifact_trace": self.artifact_trace,
      "export_paths": self.export_paths,
      "candidate_information_only": self.candidate_information_only,
      "human_review_required": self.human_review_required,
      "supporting_evidence_candidate_only": self.supporting_evidence_candidate_only,
      "evidence_map_not_proof": self.evidence_map_not_proof,
      "gap_is_not_invalidity": self.gap_is_not_invalidity,
      "no_legal_judgement": self.no_legal_judgement,
      "no_email_send": self.no_email_send,
      "no_scheduler_start": self.no_scheduler_start,
      "warnings": self.warnings,
    }


@dataclass
class V8DemoPolishExport:
  export_id: str
  output_dir: str
  json_path: str
  md_path: str
  manifest_path: str
  story_cards_csv_path: str
  narrative_path: str
  caveats_path: str
  created_at: str
  excel_warning: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)
