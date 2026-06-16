"""Technical assessment domain models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TechnicalAssessmentItem:
  publication_number: str
  patent_title: str | None
  assignee: str | None
  technical_topic: str
  assessment_type: str
  assessment: str
  technical_confidence: str
  technical_score: float
  element_id: str | None = None
  element_type: str | None = None
  evidence_basis: list[str] = field(default_factory=list)
  supporting_evidence_count: int = 0
  background_evidence_count: int = 0
  evidence_gap_count: int = 0
  uncertainty: str = ""
  recommended_check: str = ""
  recommended_reader_action: str = ""
  caveat: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> TechnicalAssessmentItem:
    return cls(
      publication_number=str(data.get("publication_number", "")),
      patent_title=data.get("patent_title"),
      assignee=data.get("assignee"),
      element_id=data.get("element_id"),
      element_type=data.get("element_type"),
      technical_topic=str(data.get("technical_topic", "")),
      assessment_type=str(data.get("assessment_type", "")),
      assessment=str(data.get("assessment", "")),
      technical_confidence=str(data.get("technical_confidence", "unknown")),
      technical_score=float(data.get("technical_score", 0.0)),
      evidence_basis=list(data.get("evidence_basis", [])),
      supporting_evidence_count=int(data.get("supporting_evidence_count", 0)),
      background_evidence_count=int(data.get("background_evidence_count", 0)),
      evidence_gap_count=int(data.get("evidence_gap_count", 0)),
      uncertainty=str(data.get("uncertainty", "")),
      recommended_check=str(data.get("recommended_check", "")),
      recommended_reader_action=str(data.get("recommended_reader_action", "")),
      caveat=str(data.get("caveat", "")),
    )


@dataclass
class PatentTechnicalAssessment:
  publication_number: str
  patent_title: str | None = None
  assignee: str | None = None
  overall_technical_score: float = 0.0
  overall_technical_confidence: str = "unknown"
  technical_summary: str = ""
  strongest_supported_points: list[str] = field(default_factory=list)
  weak_or_uncertain_points: list[str] = field(default_factory=list)
  key_evidence_gaps: list[str] = field(default_factory=list)
  implementation_risks: list[str] = field(default_factory=list)
  measurement_or_validation_risks: list[str] = field(default_factory=list)
  recommended_next_checks: list[str] = field(default_factory=list)
  recommended_reader_action: str = ""
  assessment_items: list[TechnicalAssessmentItem] = field(default_factory=list)
  caveats: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return {
      **asdict(self),
      "assessment_items": [item.to_dict() for item in self.assessment_items],
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> PatentTechnicalAssessment:
    items = [
      TechnicalAssessmentItem.from_dict(item) if isinstance(item, dict) else item
      for item in data.get("assessment_items", [])
    ]
    return cls(
      publication_number=str(data.get("publication_number", "")),
      patent_title=data.get("patent_title"),
      assignee=data.get("assignee"),
      overall_technical_score=float(data.get("overall_technical_score", 0.0)),
      overall_technical_confidence=str(data.get("overall_technical_confidence", "unknown")),
      technical_summary=str(data.get("technical_summary", "")),
      strongest_supported_points=list(data.get("strongest_supported_points", [])),
      weak_or_uncertain_points=list(data.get("weak_or_uncertain_points", [])),
      key_evidence_gaps=list(data.get("key_evidence_gaps", [])),
      implementation_risks=list(data.get("implementation_risks", [])),
      measurement_or_validation_risks=list(data.get("measurement_or_validation_risks", [])),
      recommended_next_checks=list(data.get("recommended_next_checks", [])),
      recommended_reader_action=str(data.get("recommended_reader_action", "")),
      assessment_items=items,
      caveats=list(data.get("caveats", [])),
    )
