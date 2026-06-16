"""Normalized patent record for seed analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


def _safe_str(value: Any) -> str | None:
  if value is None:
    return None
  text = str(value).strip()
  return text or None


@dataclass
class PatentRecord:
  publication_number: str
  title: str
  abstract: str | None = None
  assignee: str | None = None
  publication_date: str | None = None
  country: str | None = None
  claims: str | None = None
  description: str | None = None
  examples: str | None = None
  measured_properties: str | None = None
  source_type: str | None = None
  evidence_level: str | None = None

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> PatentRecord:
    data = data or {}
    return cls(
      publication_number=_safe_str(data.get("publication_number")) or "",
      title=_safe_str(data.get("title")) or "",
      abstract=_safe_str(data.get("abstract")),
      assignee=_safe_str(data.get("assignee")),
      publication_date=_safe_str(data.get("publication_date")),
      country=_safe_str(data.get("country")),
      claims=_safe_str(data.get("claims")),
      description=_safe_str(data.get("description")),
      examples=_safe_str(data.get("examples")),
      measured_properties=_safe_str(data.get("measured_properties")),
      source_type=_safe_str(data.get("source_type")),
      evidence_level=_safe_str(data.get("evidence_level")),
    )

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  def combined_text(self) -> str:
    parts = [
      self.title,
      self.abstract,
      self.assignee,
      self.claims,
      self.description,
      self.examples,
      self.measured_properties,
    ]
    return " ".join(part for part in parts if part).lower()
