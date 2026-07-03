"""Lightweight signal and watch profile models for v9."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .watch_profile_schema import default_bilingual_watch_profile, migrate_watch_profile

VALID_SIGNAL_TYPES = ("patent", "paper", "web", "company")
VALID_STATUSES = ("New", "Rising", "Dropped", "Stable")
VALID_ACTIONS = ("Read Now", "Watch", "Ignore")


def _to_optional_float(value: Any) -> float | None:
  if value is None or value == "":
    return None
  return float(value)


@dataclass(slots=True)
class Signal:
  id: str
  title: str
  type: str
  source_url: str
  source_name: str
  published_date: str
  summary: str
  score: float
  previous_score: float | None
  status: str
  action: str
  why_read: str
  what_to_check: str
  next_action: str
  tags: list[str] = field(default_factory=list)
  companies: list[str] = field(default_factory=list)
  language: str = ""
  memo: str = ""

  @classmethod
  def from_dict(cls, raw: dict[str, Any]) -> "Signal":
    return cls(
      id=str(raw.get("id", "")).strip(),
      title=str(raw.get("title", "")).strip(),
      type=str(raw.get("type", "")).strip().lower(),
      source_url=str(raw.get("source_url", "")).strip(),
      source_name=str(raw.get("source_name", "")).strip(),
      published_date=str(raw.get("published_date", "")).strip(),
      summary=str(raw.get("summary", "")).strip(),
      score=float(raw.get("score", 0.0) or 0.0),
      previous_score=_to_optional_float(raw.get("previous_score")),
      status=str(raw.get("status", "Stable")).strip(),
      action=str(raw.get("action", "Watch")).strip(),
      why_read=str(raw.get("why_read", "")).strip(),
      what_to_check=str(raw.get("what_to_check", "")).strip(),
      next_action=str(raw.get("next_action", "")).strip(),
      tags=[str(tag).strip() for tag in raw.get("tags", []) if str(tag).strip()],
      companies=[str(company).strip() for company in raw.get("companies", []) if str(company).strip()],
      language=str(raw.get("language", "")).strip(),
      memo=str(raw.get("memo", "")).strip(),
    )

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass(slots=True)
class WatchProfile:
  schema_version: str = "v9.2"
  theme_name: str = ""
  theme_description: str = ""
  keywords: dict[str, list[str]] = field(default_factory=lambda: default_bilingual_watch_profile()["keywords"])
  seed_publications: list[str] = field(default_factory=list)
  candidate_publications: list[str] = field(default_factory=list)
  target_companies: list[str] = field(default_factory=list)
  source_types: list[str] = field(default_factory=list)
  countries: list[str] = field(default_factory=list)
  cadence: str = "weekly"
  priority_rules: list[str] = field(default_factory=list)
  notes: str = ""

  @classmethod
  def from_dict(cls, raw: dict[str, Any]) -> "WatchProfile":
    migrated = migrate_watch_profile(raw)
    return cls(
      schema_version=str(migrated.get("schema_version", "v9.2")).strip(),
      theme_name=str(migrated.get("theme_name", "")).strip(),
      theme_description=str(migrated.get("theme_description", "")).strip(),
      keywords={key: list(value) for key, value in dict(migrated.get("keywords", {})).items()},
      seed_publications=[str(item).strip() for item in migrated.get("seed_publications", []) if str(item).strip()],
      candidate_publications=[str(item).strip() for item in migrated.get("candidate_publications", []) if str(item).strip()],
      target_companies=[str(item).strip() for item in migrated.get("target_companies", []) if str(item).strip()],
      source_types=[str(item).strip().lower() for item in migrated.get("source_types", []) if str(item).strip()],
      countries=[str(item).strip() for item in migrated.get("countries", []) if str(item).strip()],
      cadence=str(migrated.get("cadence", "weekly")).strip().lower(),
      priority_rules=[str(item).strip() for item in migrated.get("priority_rules", []) if str(item).strip()],
      notes=str(migrated.get("notes", "")).strip(),
    )

  def to_dict(self) -> dict[str, Any]:
    return migrate_watch_profile(asdict(self))

  @property
  def theme(self) -> str:
    return self.theme_name

  @property
  def include_keywords(self) -> list[str]:
    ordered_keys = (
      "core_en",
      "core_ja",
      "application_en",
      "application_ja",
      "material_process_en",
      "material_process_ja",
    )
    combined: list[str] = []
    for key in ordered_keys:
      combined.extend(self.keywords.get(key, []))
    return combined

  @property
  def exclude_keywords(self) -> list[str]:
    return list(self.keywords.get("exclude_en", [])) + list(self.keywords.get("exclude_ja", []))
