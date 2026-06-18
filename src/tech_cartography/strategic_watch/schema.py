"""Strategic Watch Brief schema (Phase 23.5)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

WATCH_TYPES: frozenset[str] = frozenset(
  {
    "patent_paper_web_signal",
    "national_project_signal",
    "money_signal",
    "ir_disclosure_signal",
    "company_signal",
    "local_news_signal",
    "evidence_gap",
    "next_action",
  },
)

WATCH_PRIORITIES: frozenset[str] = frozenset({"high", "medium", "low"})

LINK_CONFIDENCES: frozenset[str] = frozenset({"medium", "low", "weak", "unknown"})

BRIEF_CAUTION = (
  "This is a Strategic Watch Brief, not a final conclusion.\n"
  "Web signals are signal candidates, not final conclusions.\n"
  "Papers are supporting evidence candidates, not proof of patent claims.\n"
  "This is not FTO, infringement, or validity analysis.\n"
  "IR / disclosure signals require document-level verification.\n"
  "Money / national_project signals require source verification.\n"
  "Synthetic demo signal must be clearly labeled."
)

ITEM_CAVEAT = (
  "This is a Strategic Watch Candidate, not a final conclusion. "
  "This is not FTO, infringement, or validity analysis. "
  "Web signals require human verification. "
  "Papers are supporting evidence candidates, not proof of patent claims."
)

WATCH_PRIORITY_NOTE = (
  "watch_priority=high means elevated monitoring attention, not confirmed fact."
)


@dataclass
class StrategicWatchItem:
  watch_id: str
  publication_number: str
  watch_theme: str
  watch_type: str
  target_patent: str
  related_claim_element: str | None
  related_paper_title: str | None
  related_web_signal_title: str | None
  related_web_signal_url: str | None
  related_web_signal_domain: str | None
  source_quality: str
  link_type: str | None
  link_score: int
  link_confidence: str
  watch_priority: str
  why_it_matters: str
  evidence_basis: str
  evidence_gap: str
  next_verification_action: str
  caveat: str
  is_synthetic_demo: bool = False

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class StrategicWatchBrief:
  publication_number: str
  created_at: str
  brief_title: str
  executive_summary: str
  watch_items: list[StrategicWatchItem]
  top_watch_items: list[StrategicWatchItem]
  evidence_gaps: list[str]
  next_actions: list[str]
  input_artifacts: dict[str, str] = field(default_factory=dict)
  caveats: list[str] = field(default_factory=list)
  notes: str = ""

  def to_dict(self) -> dict[str, Any]:
    return {
      "publication_number": self.publication_number,
      "created_at": self.created_at,
      "brief_title": self.brief_title,
      "executive_summary": self.executive_summary,
      "watch_items": [item.to_dict() for item in self.watch_items],
      "top_watch_items": [item.to_dict() for item in self.top_watch_items],
      "evidence_gaps": list(self.evidence_gaps),
      "next_actions": list(self.next_actions),
      "input_artifacts": dict(self.input_artifacts),
      "caveats": list(self.caveats),
      "notes": self.notes,
    }
