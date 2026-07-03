"""Lightweight signal and watch profile models for v9."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

VALID_SIGNAL_TYPES = ("patent", "paper", "web", "company")
VALID_STATUSES = ("New", "Rising", "Dropped", "Stable")
VALID_ACTIONS = ("Read Now", "Watch", "Ignore")


@dataclass(slots=True)
class Signal:
  id: str
  title: str
  type: str
  source_url: str
  source_name: str
  published_date: str
  score: float
  previous_score: float | None
  status: str
  action: str
  why_read: str
  what_to_check: str
  next_action: str
  tags: list[str] = field(default_factory=list)
  companies: list[str] = field(default_factory=list)

  @classmethod
  def from_dict(cls, raw: dict[str, Any]) -> "Signal":
    return cls(
      id=str(raw.get("id", "")).strip(),
      title=str(raw.get("title", "")).strip(),
      type=str(raw.get("type", "")).strip().lower(),
      source_url=str(raw.get("source_url", "")).strip(),
      source_name=str(raw.get("source_name", "")).strip(),
      published_date=str(raw.get("published_date", "")).strip(),
      score=float(raw.get("score", 0.0)),
      previous_score=None if raw.get("previous_score") is None else float(raw.get("previous_score")),
      status=str(raw.get("status", "Stable")).strip(),
      action=str(raw.get("action", "Watch")).strip(),
      why_read=str(raw.get("why_read", "")).strip(),
      what_to_check=str(raw.get("what_to_check", "")).strip(),
      next_action=str(raw.get("next_action", "")).strip(),
      tags=[str(tag).strip() for tag in raw.get("tags", []) if str(tag).strip()],
      companies=[str(company).strip() for company in raw.get("companies", []) if str(company).strip()],
    )

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass(slots=True)
class WatchProfile:
  theme: str
  include_keywords: list[str] = field(default_factory=list)
  exclude_keywords: list[str] = field(default_factory=list)
  target_companies: list[str] = field(default_factory=list)
  source_types: list[str] = field(default_factory=list)
  countries: list[str] = field(default_factory=list)
  cadence: str = "Weekly"
  priority_rules: list[str] = field(default_factory=list)

  @classmethod
  def from_dict(cls, raw: dict[str, Any]) -> "WatchProfile":
    return cls(
      theme=str(raw.get("theme", "")).strip(),
      include_keywords=[str(item).strip() for item in raw.get("include_keywords", []) if str(item).strip()],
      exclude_keywords=[str(item).strip() for item in raw.get("exclude_keywords", []) if str(item).strip()],
      target_companies=[str(item).strip() for item in raw.get("target_companies", []) if str(item).strip()],
      source_types=[str(item).strip().lower() for item in raw.get("source_types", []) if str(item).strip()],
      countries=[str(item).strip() for item in raw.get("countries", []) if str(item).strip()],
      cadence=str(raw.get("cadence", "Weekly")).strip(),
      priority_rules=[str(item).strip() for item in raw.get("priority_rules", []) if str(item).strip()],
    )

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)
