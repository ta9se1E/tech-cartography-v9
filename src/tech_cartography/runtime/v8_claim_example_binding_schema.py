"""Claim-example binding schema (Phase 27S.4 / 27S.5.4)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

CLAIM_EXAMPLE_BINDING_NOTICES: tuple[str, ...] = (
  "対応付けは候補であり、確定・裏取り完了ではありません。",
  "support_level は確認優先度であり、法的評価ではありません。",
  "needs_human_review=True が基本です。Evidenceは証明ではなく裏取り候補です。",
  "Gapは弱点ではなく未確認事項です。",
  "OCR由来の数値・単位・実施例番号は必ず原文PDFで確認してください。",
)

VALID_SUPPORT_TYPES: tuple[str, ...] = (
  "process_support_candidate",
  "process_condition_candidate",
  "property_support_candidate",
  "structure_support_candidate",
  "table_support_candidate",
  "comparison_support_candidate",
  "mixed_support_candidate",
  "publication_level_support_candidate",
  "partial_example_support_candidate",
  "no_example_support_candidate",
  "not_enough_information",
)

VALID_SUPPORT_LEVELS: tuple[str, ...] = (
  "high_candidate",
  "medium_candidate",
  "low_candidate",
  "none",
  "needs_review",
)


@dataclass
class ClaimExampleLink:
  case_id: str
  publication_number: str
  claim_no: str
  claim_text: str
  support_type: str
  support_level: str
  matched_elements: list[str]
  missing_elements: list[str]
  matched_user_keywords: list[str]
  evidence_texts: list[str]
  reason: str
  confidence: float
  needs_human_review: bool
  binding_method: str
  example_id: str | None = None
  example_label: str | None = None
  linked_fact_ids: list[str] = field(default_factory=list)
  warning: str | None = None
  matched_fact_types: list[str] = field(default_factory=list)
  matched_fact_count: int = 0
  process_match_count: int = 0
  property_match_count: int = 0
  structure_match_count: int = 0
  table_match_count: int = 0
  comparison_match_count: int = 0
  selected_example_score: int = 0
  top_evidence_snippets: list[str] = field(default_factory=list)
  process_evidence_texts: list[str] = field(default_factory=list)
  property_evidence_texts: list[str] = field(default_factory=list)
  structure_evidence_texts: list[str] = field(default_factory=list)
  table_evidence_texts: list[str] = field(default_factory=list)
  comparison_evidence_texts: list[str] = field(default_factory=list)
  source_example_facts_csv: str | None = None
  binding_version: str = "phase27s54"

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class ClaimExampleBindingResult:
  case_id: str
  publication_number: str
  claim_count: int = 0
  linked_claim_count: int = 0
  unlinked_claim_count: int = 0
  link_count: int = 0
  strong_candidate_count: int = 0
  partial_candidate_count: int = 0
  property_candidate_count: int = 0
  comparison_candidate_count: int = 0
  no_candidate_count: int = 0
  process_support_count: int = 0
  property_support_count: int = 0
  structure_support_count: int = 0
  table_support_count: int = 0
  comparison_support_count: int = 0
  mixed_support_count: int = 0
  publication_level_support_count: int = 0
  linked_fact_count: int = 0
  linked_example_count: int = 0
  source_example_facts_csv: str | None = None
  needs_human_review: bool = True
  links: list[ClaimExampleLink] = field(default_factory=list)
  output_dir: str | None = None
  status: str = "ok"
  warning: str | None = None

  def to_dict(self) -> dict[str, Any]:
    return {
      "case_id": self.case_id,
      "publication_number": self.publication_number,
      "claim_count": self.claim_count,
      "linked_claim_count": self.linked_claim_count,
      "unlinked_claim_count": self.unlinked_claim_count,
      "link_count": self.link_count,
      "strong_candidate_count": self.strong_candidate_count,
      "partial_candidate_count": self.partial_candidate_count,
      "property_candidate_count": self.property_candidate_count,
      "comparison_candidate_count": self.comparison_candidate_count,
      "no_candidate_count": self.no_candidate_count,
      "process_support_count": self.process_support_count,
      "property_support_count": self.property_support_count,
      "structure_support_count": self.structure_support_count,
      "table_support_count": self.table_support_count,
      "comparison_support_count": self.comparison_support_count,
      "mixed_support_count": self.mixed_support_count,
      "publication_level_support_count": self.publication_level_support_count,
      "linked_fact_count": self.linked_fact_count,
      "linked_example_count": self.linked_example_count,
      "source_example_facts_csv": self.source_example_facts_csv,
      "needs_human_review": self.needs_human_review,
      "links": [link.to_dict() for link in self.links],
      "output_dir": self.output_dir,
      "status": self.status,
      "warning": self.warning,
    }
