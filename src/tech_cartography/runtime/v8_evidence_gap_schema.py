"""Evidence-aware Gap / Next Actions schema (Phase 27S.6)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tech_cartography.runtime.v8_sources_schema import utc_now_iso

GENERATION_METHOD = "claim_example_evidence_phase27s6"
BINDING_VERSION_EXPECTED = "phase27s54"

EVIDENCE_GAP_SAFETY_NOTICES: tuple[str, ...] = (
  "Gapは弱点ではなく、未確認事項です。",
  "Evidenceは証明ではなく、裏取り候補です。",
  "OCR由来の数値・単位・表は原文確認が必要です。",
  "本ツールは特許の有効性・侵害・FTOを判断しません。",
  "Claim-Example bindingは対応候補であり、法的判断ではありません。",
)

GAP_TYPE_NO_EXAMPLE_FACTS = "no_example_facts_gap"
GAP_TYPE_CLAIM_EXAMPLE_LINK = "claim_example_link_gap"
GAP_TYPE_OCR_HUMAN_REVIEW = "ocr_human_review_gap"
GAP_TYPE_PROPERTY_VALUE_REVIEW = "property_value_review_gap"
GAP_TYPE_TABLE_REVIEW = "table_review_gap"
GAP_TYPE_PROCESS_CONDITION_REVIEW = "process_condition_review_gap"
GAP_TYPE_STRUCTURE_PROPERTY_REVIEW = "structure_property_review_gap"
GAP_TYPE_PAPER_EVIDENCE = "paper_evidence_gap"
GAP_TYPE_READY_FOR_HUMAN_REVIEW = "ready_for_human_review"

VALID_GAP_TYPES: tuple[str, ...] = (
  GAP_TYPE_NO_EXAMPLE_FACTS,
  GAP_TYPE_CLAIM_EXAMPLE_LINK,
  GAP_TYPE_OCR_HUMAN_REVIEW,
  GAP_TYPE_PROPERTY_VALUE_REVIEW,
  GAP_TYPE_TABLE_REVIEW,
  GAP_TYPE_PROCESS_CONDITION_REVIEW,
  GAP_TYPE_STRUCTURE_PROPERTY_REVIEW,
  GAP_TYPE_PAPER_EVIDENCE,
  GAP_TYPE_READY_FOR_HUMAN_REVIEW,
)

VALID_GAP_SEVERITIES: tuple[str, ...] = (
  "high_review_priority",
  "medium_review_priority",
  "low_review_priority",
  "info",
)

VALID_ACTION_PRIORITIES: tuple[str, ...] = ("P1", "P2", "P3")

VALID_EVIDENCE_STATUSES: tuple[str, ...] = (
  "no_example_facts",
  "candidate_found_needs_review",
  "ocr_candidate_needs_review",
  "property_candidate_needs_review",
  "table_candidate_needs_review",
  "ready_for_human_review",
)

GAP_NEXT_ACTIONS_CSV_COLUMNS: tuple[str, ...] = (
  "case_id",
  "publication_number",
  "claim_no",
  "gap_id",
  "gap_type",
  "gap_severity",
  "gap_label",
  "gap_description",
  "next_action",
  "action_owner",
  "action_priority",
  "evidence_status",
  "support_type",
  "support_level",
  "matched_fact_types",
  "matched_elements",
  "missing_elements",
  "top_evidence_snippets",
  "linked_fact_ids",
  "source_claim_example_links_csv",
  "source_example_facts_csv",
  "needs_human_review",
  "generation_method",
  "warning",
)

GAP_SUMMARY_CSV_COLUMNS: tuple[str, ...] = (
  "case_id",
  "publication_number",
  "claim_count",
  "gap_count",
  "p1_action_count",
  "p2_action_count",
  "p3_action_count",
  "no_example_facts_gap_count",
  "ocr_human_review_gap_count",
  "property_value_review_gap_count",
  "table_review_gap_count",
  "process_condition_review_gap_count",
  "structure_property_review_gap_count",
  "ready_for_human_review_count",
  "needs_human_review",
  "status",
  "warning",
)

FORBIDDEN_GAP_WORDS: frozenset[str] = frozenset({
  "証明済み",
  "裏取り完了",
  "権利範囲を支える",
  "侵害判断",
  "FTO判断",
  "有効性判断",
  "弱点",
  "無効理由",
  "リスク確定",
  "実施確定",
  "支えています",
  "証明しています",
})


@dataclass
class EvidenceAwareGapRecord:
  case_id: str
  publication_number: str
  claim_no: str
  gap_id: str
  gap_type: str
  gap_severity: str
  gap_label: str
  gap_description: str
  next_action: str
  action_owner: str = "researcher"
  action_priority: str = "P2"
  evidence_status: str = "candidate_found_needs_review"
  support_type: str = ""
  support_level: str = ""
  matched_fact_types: str = ""
  matched_elements: str = ""
  missing_elements: str = ""
  top_evidence_snippets: str = ""
  linked_fact_ids: str = ""
  source_claim_example_links_csv: str = ""
  source_example_facts_csv: str = ""
  needs_human_review: bool = True
  generation_method: str = GENERATION_METHOD
  warning: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class EvidenceAwareGapSummary:
  case_id: str
  publication_number: str
  claim_count: int = 0
  gap_count: int = 0
  p1_action_count: int = 0
  p2_action_count: int = 0
  p3_action_count: int = 0
  no_example_facts_gap_count: int = 0
  ocr_human_review_gap_count: int = 0
  property_value_review_gap_count: int = 0
  table_review_gap_count: int = 0
  process_condition_review_gap_count: int = 0
  structure_property_review_gap_count: int = 0
  ready_for_human_review_count: int = 0
  needs_human_review: bool = True
  status: str = "ok"
  warning: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class EvidenceAwareGapReport:
  case_id: str
  generated_at: str = field(default_factory=utc_now_iso)
  binding_version: str = ""
  source_claim_example_links_dir: str = ""
  source_claim_example_links_csv: str = ""
  source_binding_summary_csv: str = ""
  source_example_facts_csv: str = ""
  gaps: list[EvidenceAwareGapRecord] = field(default_factory=list)
  summaries: list[EvidenceAwareGapSummary] = field(default_factory=list)
  warnings: list[str] = field(default_factory=list)
  generation_method: str = GENERATION_METHOD

  @property
  def gap_count(self) -> int:
    return len(self.gaps)

  def to_dict(self) -> dict[str, Any]:
    return {
      "case_id": self.case_id,
      "generated_at": self.generated_at,
      "binding_version": self.binding_version,
      "source_claim_example_links_dir": self.source_claim_example_links_dir,
      "source_claim_example_links_csv": self.source_claim_example_links_csv,
      "source_binding_summary_csv": self.source_binding_summary_csv,
      "source_example_facts_csv": self.source_example_facts_csv,
      "gaps": [g.to_dict() for g in self.gaps],
      "summaries": [s.to_dict() for s in self.summaries],
      "warnings": self.warnings,
      "generation_method": self.generation_method,
      "gap_count": self.gap_count,
    }
