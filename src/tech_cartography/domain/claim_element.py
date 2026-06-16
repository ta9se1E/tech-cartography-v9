"""Claim element domain model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ClaimElement:
  element_id: str
  publication_number: str
  claim_number: str | None
  element_type: str
  element_text: str
  normalized_terms: list[str] = field(default_factory=list)
  source_section: str = "claims"
  evidence_snippet: str = ""
  confidence: float = 0.5
  support_status: str = "unclear"
  support_sections: list[str] = field(default_factory=list)
  notes: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> ClaimElement:
    return cls(
      element_id=str(data.get("element_id", "")),
      publication_number=str(data.get("publication_number", "")),
      claim_number=data.get("claim_number"),
      element_type=str(data.get("element_type", "unknown")),
      element_text=str(data.get("element_text", "")),
      normalized_terms=list(data.get("normalized_terms", [])),
      source_section=str(data.get("source_section", "claims")),
      evidence_snippet=str(data.get("evidence_snippet", "")),
      confidence=float(data.get("confidence", 0.5)),
      support_status=str(data.get("support_status", "unclear")),
      support_sections=list(data.get("support_sections", [])),
      notes=list(data.get("notes", [])),
    )
