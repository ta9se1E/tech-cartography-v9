"""Claim-example binding schema (Phase 27S.4)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

CLAIM_EXAMPLE_BINDING_NOTICES: tuple[str, ...] = (
  "対応付けは候補であり、確定・裏取り完了ではありません。",
  "support_level は確認優先度であり、法的評価ではありません。",
  "needs_human_review=True が基本です。Evidenceは証明ではなく裏取り候補です。",
  "Gapは弱点ではなく未確認事項です。",
)

VALID_SUPPORT_TYPES: tuple[str, ...] = (
  "process_condition_candidate",
  "property_support_candidate",
  "comparison_support_candidate",
  "table_support_candidate",
  "structure_support_candidate",
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
      "needs_human_review": self.needs_human_review,
      "links": [link.to_dict() for link in self.links],
      "output_dir": self.output_dir,
      "status": self.status,
      "warning": self.warning,
    }
