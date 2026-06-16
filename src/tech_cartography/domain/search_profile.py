"""User-defined search profile for evidence map retrieval."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _as_str_list(value: Any) -> list[str]:
  if value is None:
    return []
  if isinstance(value, (list, tuple, set)):
    return [str(item).strip() for item in value if str(item).strip()]
  text = str(value).strip()
  if not text:
    return []
  if "," in text:
    return [part.strip() for part in text.split(",") if part.strip()]
  return [text]


def _dedupe_terms(terms: list[str]) -> list[str]:
  seen: set[str] = set()
  deduped: list[str] = []
  for term in terms:
    key = term.lower()
    if key in seen:
      continue
    seen.add(key)
    deduped.append(term)
  return deduped


@dataclass
class SearchProfile:
  theme: str
  invention_note: str | None = None
  materials: list[str] = field(default_factory=list)
  processes: list[str] = field(default_factory=list)
  properties: list[str] = field(default_factory=list)
  applications: list[str] = field(default_factory=list)
  companies: list[str] = field(default_factory=list)
  countries: list[str] = field(default_factory=list)
  include_terms: list[str] = field(default_factory=list)
  exclude_terms: list[str] = field(default_factory=list)
  year_min: int | None = None
  year_max: int | None = None
  search_goal: str = "carbon fiber evidence map"
  max_results_total: int = 500
  max_results_per_intent: int = 100

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> SearchProfile:
    data = data or {}
    year_min = data.get("year_min")
    year_max = data.get("year_max")
    if year_min is None and isinstance(data.get("year_range"), dict):
      year_min = data["year_range"].get("year_min")
    if year_max is None and isinstance(data.get("year_range"), dict):
      year_max = data["year_range"].get("year_max")

    return cls(
      theme=str(data.get("theme", "")).strip(),
      invention_note=data.get("invention_note"),
      materials=_dedupe_terms(_as_str_list(data.get("materials"))),
      processes=_dedupe_terms(_as_str_list(data.get("processes"))),
      properties=_dedupe_terms(_as_str_list(data.get("properties"))),
      applications=_dedupe_terms(_as_str_list(data.get("applications"))),
      companies=_dedupe_terms(_as_str_list(data.get("companies"))),
      countries=_dedupe_terms(_as_str_list(data.get("countries"))),
      include_terms=_dedupe_terms(_as_str_list(data.get("include_terms"))),
      exclude_terms=_dedupe_terms(_as_str_list(data.get("exclude_terms"))),
      year_min=int(year_min) if year_min is not None else None,
      year_max=int(year_max) if year_max is not None else None,
      search_goal=str(data.get("search_goal", "carbon fiber evidence map")).strip(),
      max_results_total=int(data.get("max_results_total", 500)),
      max_results_per_intent=int(data.get("max_results_per_intent", 100)),
    )

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  def normalized_terms(self) -> dict[str, list[str]]:
    return {
      "materials": _dedupe_terms(self.materials),
      "processes": _dedupe_terms(self.processes),
      "properties": _dedupe_terms(self.properties),
      "applications": _dedupe_terms(self.applications),
      "companies": _dedupe_terms(self.companies),
      "countries": _dedupe_terms(self.countries),
      "include_terms": _dedupe_terms(self.include_terms),
      "exclude_terms": _dedupe_terms(self.exclude_terms),
    }
