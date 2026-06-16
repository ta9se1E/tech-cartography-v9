"""Web / company signal domain model."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


def new_signal_id() -> str:
  return f"ws-{uuid.uuid4().hex[:10]}"


@dataclass
class WebSignal:
  signal_id: str
  company: str
  normalized_company: str
  source_title: str
  signal_type: str = "unknown"
  signal_date: str | None = None
  source_url: str | None = None
  source_name: str | None = None
  display_url: str | None = None
  technology_terms: list[str] = field(default_factory=list)
  summary: str | None = None
  business_signal: str | None = None
  confidence: float | None = 0.5
  source_note: str | None = None
  source_quality_level: str | None = None
  source_quality_score: float | None = None
  warnings: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> WebSignal:
    confidence = data.get("confidence")
    quality_score = data.get("source_quality_score")
    return cls(
      signal_id=str(data.get("signal_id") or new_signal_id()),
      company=str(data.get("company", "")),
      normalized_company=str(data.get("normalized_company") or data.get("company", "")),
      source_title=str(data.get("source_title", "")),
      signal_type=str(data.get("signal_type") or "unknown"),
      signal_date=data.get("signal_date"),
      source_url=data.get("source_url"),
      source_name=data.get("source_name"),
      display_url=data.get("display_url"),
      technology_terms=list(data.get("technology_terms", [])),
      summary=data.get("summary"),
      business_signal=data.get("business_signal"),
      confidence=float(confidence) if confidence not in (None, "") else 0.5,
      source_note=data.get("source_note"),
      source_quality_level=data.get("source_quality_level"),
      source_quality_score=float(quality_score) if quality_score not in (None, "") else None,
      warnings=list(data.get("warnings", [])),
    )
