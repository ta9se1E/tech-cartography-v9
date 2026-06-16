"""Query plan model for intent-specific patent retrieval."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class QueryPlan:
  intent_id: str
  purpose: str
  query_hint: str
  must_have_terms: list[str] = field(default_factory=list)
  should_have_terms: list[str] = field(default_factory=list)
  exclude_terms: list[str] = field(default_factory=list)
  target_companies: list[str] = field(default_factory=list)
  target_countries: list[str] = field(default_factory=list)
  year_min: int | None = None
  year_max: int | None = None
  recommended_bigquery_mode: str = "lightweight"
  expected_noise_risk: str = "Medium"
  max_results: int = 100
  notes: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> QueryPlan:
    return cls(
      intent_id=str(data.get("intent_id", "")),
      purpose=str(data.get("purpose", "")),
      query_hint=str(data.get("query_hint", "")),
      must_have_terms=list(data.get("must_have_terms", [])),
      should_have_terms=list(data.get("should_have_terms", [])),
      exclude_terms=list(data.get("exclude_terms", [])),
      target_companies=list(data.get("target_companies", [])),
      target_countries=list(data.get("target_countries", [])),
      year_min=data.get("year_min"),
      year_max=data.get("year_max"),
      recommended_bigquery_mode=str(
        data.get("recommended_bigquery_mode", "lightweight"),
      ),
      expected_noise_risk=str(data.get("expected_noise_risk", "Medium")),
      max_results=int(data.get("max_results", 100)),
      notes=list(data.get("notes", [])),
    )
