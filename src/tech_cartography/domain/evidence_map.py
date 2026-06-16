"""Evidence map domain models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ClaimPaperEvidenceItem:
  publication_number: str
  patent_title: str | None
  assignee: str | None
  element_id: str
  element_type: str
  element_text: str
  normalized_terms: list[str] = field(default_factory=list)
  claim_support_status: str = "unclear"
  paper_id: str | None = None
  paper_title: str | None = None
  paper_year: int | None = None
  source_name: str | None = None
  doi: str | None = None
  display_url: str | None = None
  source_quality_level: str | None = None
  source_quality_score: float | None = None
  evidence_relation: str = "no_paper_evidence"
  evidence_confidence: str = "unknown"
  evidence_score: float = 0.0
  matched_terms: list[str] = field(default_factory=list)
  relation_reason: str = ""
  caveat: str = ""
  recommended_human_check: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> ClaimPaperEvidenceItem:
    return cls(
      publication_number=str(data.get("publication_number", "")),
      patent_title=data.get("patent_title"),
      assignee=data.get("assignee"),
      element_id=str(data.get("element_id", "")),
      element_type=str(data.get("element_type", "unknown")),
      element_text=str(data.get("element_text", "")),
      normalized_terms=list(data.get("normalized_terms", [])),
      claim_support_status=str(data.get("claim_support_status", "unclear")),
      paper_id=data.get("paper_id"),
      paper_title=data.get("paper_title"),
      paper_year=int(data["paper_year"]) if data.get("paper_year") not in (None, "") else None,
      source_name=data.get("source_name"),
      doi=data.get("doi"),
      display_url=data.get("display_url"),
      source_quality_level=data.get("source_quality_level"),
      source_quality_score=float(data["source_quality_score"])
      if data.get("source_quality_score") not in (None, "")
      else None,
      evidence_relation=str(data.get("evidence_relation", "no_paper_evidence")),
      evidence_confidence=str(data.get("evidence_confidence", "unknown")),
      evidence_score=float(data.get("evidence_score", 0.0)),
      matched_terms=list(data.get("matched_terms", [])),
      relation_reason=str(data.get("relation_reason", "")),
      caveat=str(data.get("caveat", "")),
      recommended_human_check=str(data.get("recommended_human_check", "")),
    )


@dataclass
class PatentEvidenceMap:
  publication_number: str
  patent_title: str | None = None
  assignee: str | None = None
  evidence_level: str | None = None
  total_claim_elements: int = 0
  elements_with_supporting_papers: int = 0
  elements_with_background_papers: int = 0
  elements_without_papers: int = 0
  high_quality_sources: int = 0
  evidence_items: list[ClaimPaperEvidenceItem] = field(default_factory=list)
  evidence_summary: dict[str, Any] = field(default_factory=dict)
  caveats: list[str] = field(default_factory=list)
  next_actions: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return {
      **asdict(self),
      "evidence_items": [item.to_dict() for item in self.evidence_items],
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> PatentEvidenceMap:
    items = [
      ClaimPaperEvidenceItem.from_dict(item) if isinstance(item, dict) else item
      for item in data.get("evidence_items", [])
    ]
    return cls(
      publication_number=str(data.get("publication_number", "")),
      patent_title=data.get("patent_title"),
      assignee=data.get("assignee"),
      evidence_level=data.get("evidence_level"),
      total_claim_elements=int(data.get("total_claim_elements", 0)),
      elements_with_supporting_papers=int(data.get("elements_with_supporting_papers", 0)),
      elements_with_background_papers=int(data.get("elements_with_background_papers", 0)),
      elements_without_papers=int(data.get("elements_without_papers", 0)),
      high_quality_sources=int(data.get("high_quality_sources", 0)),
      evidence_items=items,
      evidence_summary=dict(data.get("evidence_summary", {})),
      caveats=list(data.get("caveats", [])),
      next_actions=list(data.get("next_actions", [])),
    )
