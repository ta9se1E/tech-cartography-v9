"""Business assessment domain models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class BusinessAssessmentItem:
  publication_number: str
  patent_title: str | None
  assignee: str | None
  business_topic: str
  assessment_type: str
  assessment: str
  business_confidence: str
  business_score: float
  primary_cluster_id: str | None = None
  primary_cluster_name: str | None = None
  evidence_basis: list[str] = field(default_factory=list)
  web_signal_count: int = 0
  business_signal_count: int = 0
  technical_confidence: str | None = None
  technical_score: float | None = None
  uncertainty: str = ""
  recommended_action: str = ""
  recommended_reader_action: str = ""
  caveat: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> BusinessAssessmentItem:
    return cls(
      publication_number=str(data.get("publication_number", "")),
      patent_title=data.get("patent_title"),
      assignee=data.get("assignee"),
      primary_cluster_id=data.get("primary_cluster_id"),
      primary_cluster_name=data.get("primary_cluster_name"),
      business_topic=str(data.get("business_topic", "")),
      assessment_type=str(data.get("assessment_type", "")),
      assessment=str(data.get("assessment", "")),
      business_confidence=str(data.get("business_confidence", "unknown")),
      business_score=float(data.get("business_score", 0.0)),
      evidence_basis=list(data.get("evidence_basis", [])),
      web_signal_count=int(data.get("web_signal_count", 0)),
      business_signal_count=int(data.get("business_signal_count", 0)),
      technical_confidence=data.get("technical_confidence"),
      technical_score=float(data["technical_score"]) if data.get("technical_score") not in (None, "") else None,
      uncertainty=str(data.get("uncertainty", "")),
      recommended_action=str(data.get("recommended_action", "")),
      recommended_reader_action=str(data.get("recommended_reader_action", "")),
      caveat=str(data.get("caveat", "")),
    )


@dataclass
class PatentBusinessAssessment:
  publication_number: str
  patent_title: str | None = None
  assignee: str | None = None
  primary_cluster_id: str | None = None
  primary_cluster_name: str | None = None
  overall_business_score: float = 0.0
  overall_business_confidence: str = "unknown"
  business_summary: str = ""
  commercialization_signals: list[str] = field(default_factory=list)
  competitive_watch_points: list[str] = field(default_factory=list)
  sme_opportunity_points: list[str] = field(default_factory=list)
  design_around_or_differentiation_hints: list[str] = field(default_factory=list)
  partnership_or_customer_hints: list[str] = field(default_factory=list)
  business_risks: list[str] = field(default_factory=list)
  recommended_next_actions: list[str] = field(default_factory=list)
  recommended_reader_action: str = ""
  assessment_items: list[BusinessAssessmentItem] = field(default_factory=list)
  caveats: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return {
      **asdict(self),
      "assessment_items": [item.to_dict() for item in self.assessment_items],
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> PatentBusinessAssessment:
    items = [
      BusinessAssessmentItem.from_dict(item) if isinstance(item, dict) else item
      for item in data.get("assessment_items", [])
    ]
    return cls(
      publication_number=str(data.get("publication_number", "")),
      patent_title=data.get("patent_title"),
      assignee=data.get("assignee"),
      primary_cluster_id=data.get("primary_cluster_id"),
      primary_cluster_name=data.get("primary_cluster_name"),
      overall_business_score=float(data.get("overall_business_score", 0.0)),
      overall_business_confidence=str(data.get("overall_business_confidence", "unknown")),
      business_summary=str(data.get("business_summary", "")),
      commercialization_signals=list(data.get("commercialization_signals", [])),
      competitive_watch_points=list(data.get("competitive_watch_points", [])),
      sme_opportunity_points=list(data.get("sme_opportunity_points", [])),
      design_around_or_differentiation_hints=list(data.get("design_around_or_differentiation_hints", [])),
      partnership_or_customer_hints=list(data.get("partnership_or_customer_hints", [])),
      business_risks=list(data.get("business_risks", [])),
      recommended_next_actions=list(data.get("recommended_next_actions", [])),
      recommended_reader_action=str(data.get("recommended_reader_action", "")),
      assessment_items=items,
      caveats=list(data.get("caveats", [])),
    )
