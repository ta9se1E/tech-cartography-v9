"""Full text patent record domain model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FullTextRecord:
  publication_number: str
  title: str | None = None
  assignee: str | None = None
  country: str | None = None
  url: str | None = None
  claims: str | None = None
  independent_claims: list[str] = field(default_factory=list)
  description: str | None = None
  examples: str | None = None
  measured_properties: list[str] = field(default_factory=list)
  source_route: str = "unknown"
  fulltext_source: str = "not_fetched"
  claims_source: str = "not_fetched"
  description_source: str = "not_fetched"
  examples_source: str = "not_fetched"
  measured_properties_source: str = "not_fetched"
  evidence_level: str = "metadata_only"
  evidence_coverage: dict[str, Any] = field(default_factory=dict)
  retrieval_status: str = "pending"
  warnings: list[str] = field(default_factory=list)
  errors: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> FullTextRecord:
    return cls(
      publication_number=str(data.get("publication_number", "")),
      title=data.get("title"),
      assignee=data.get("assignee"),
      country=data.get("country"),
      url=data.get("url"),
      claims=data.get("claims"),
      independent_claims=list(data.get("independent_claims", [])),
      description=data.get("description"),
      examples=data.get("examples"),
      measured_properties=list(data.get("measured_properties", [])),
      source_route=str(data.get("source_route", "unknown")),
      fulltext_source=str(data.get("fulltext_source", "not_fetched")),
      claims_source=str(data.get("claims_source", "not_fetched")),
      description_source=str(data.get("description_source", "not_fetched")),
      examples_source=str(data.get("examples_source", "not_fetched")),
      measured_properties_source=str(data.get("measured_properties_source", "not_fetched")),
      evidence_level=str(data.get("evidence_level", "metadata_only")),
      evidence_coverage=dict(data.get("evidence_coverage", {})),
      retrieval_status=str(data.get("retrieval_status", "pending")),
      warnings=list(data.get("warnings", [])),
      errors=list(data.get("errors", [])),
    )

  def has_claims(self) -> bool:
    return bool(self.claims and self.claims.strip())

  def has_description(self) -> bool:
    return bool(self.description and self.description.strip())

  def has_examples(self) -> bool:
    return bool(self.examples and self.examples.strip())
