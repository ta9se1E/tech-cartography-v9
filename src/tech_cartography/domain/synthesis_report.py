"""Synthesis report domain models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SynthesisFinding:
  finding_id: str
  finding_type: str
  title: str
  summary: str
  importance: str
  confidence: str
  related_publications: list[str] = field(default_factory=list)
  related_companies: list[str] = field(default_factory=list)
  related_clusters: list[str] = field(default_factory=list)
  evidence_basis: list[str] = field(default_factory=list)
  caveats: list[str] = field(default_factory=list)
  recommended_next_action: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> SynthesisFinding:
    return cls(
      finding_id=str(data.get("finding_id", "")),
      finding_type=str(data.get("finding_type", "")),
      title=str(data.get("title", "")),
      summary=str(data.get("summary", "")),
      importance=str(data.get("importance", "low")),
      confidence=str(data.get("confidence", "unknown")),
      related_publications=list(data.get("related_publications", [])),
      related_companies=list(data.get("related_companies", [])),
      related_clusters=list(data.get("related_clusters", [])),
      evidence_basis=list(data.get("evidence_basis", [])),
      caveats=list(data.get("caveats", [])),
      recommended_next_action=str(data.get("recommended_next_action", "")),
    )


@dataclass
class SynthesisReport:
  report_title: str
  theme: str
  generated_at: str
  executive_summary: str
  key_findings: list[SynthesisFinding] = field(default_factory=list)
  priority_patents: list[dict[str, Any]] = field(default_factory=list)
  technology_cluster_summary: list[dict[str, Any]] = field(default_factory=list)
  evidence_strength_summary: dict[str, Any] = field(default_factory=dict)
  technical_view_summary: dict[str, Any] = field(default_factory=dict)
  business_view_summary: dict[str, Any] = field(default_factory=dict)
  sme_action_plan: list[dict[str, Any]] = field(default_factory=list)
  evidence_gaps: list[dict[str, Any]] = field(default_factory=list)
  caveats: list[str] = field(default_factory=list)
  next_update_recommendations: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return {
      **asdict(self),
      "key_findings": [finding.to_dict() for finding in self.key_findings],
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> SynthesisReport:
    findings = [
      SynthesisFinding.from_dict(item) if isinstance(item, dict) else item
      for item in data.get("key_findings", [])
    ]
    return cls(
      report_title=str(data.get("report_title", "")),
      theme=str(data.get("theme", "")),
      generated_at=str(data.get("generated_at", "")),
      executive_summary=str(data.get("executive_summary", "")),
      key_findings=findings,
      priority_patents=list(data.get("priority_patents", [])),
      technology_cluster_summary=list(data.get("technology_cluster_summary", [])),
      evidence_strength_summary=dict(data.get("evidence_strength_summary", {})),
      technical_view_summary=dict(data.get("technical_view_summary", {})),
      business_view_summary=dict(data.get("business_view_summary", {})),
      sme_action_plan=list(data.get("sme_action_plan", [])),
      evidence_gaps=list(data.get("evidence_gaps", [])),
      caveats=list(data.get("caveats", [])),
      next_update_recommendations=list(data.get("next_update_recommendations", [])),
    )
