"""Theme-based ranking policy schema (Phase 27R.4) — reading priority only."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

THEME_RANKING_SAFETY_NOTICES: tuple[str, ...] = (
  "スコアは読む優先度であり、法的価値・権利範囲評価・特許価値ではありません。",
  "FTO、侵害、有効性判断、法的結論は行いません。",
  "Ranking Policy は研究テーマに基づく再現可能なルールベース heuristic です。",
)


@dataclass
class ThemeRankingWeight:
  component: str
  weight: float
  label_ja: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class ThemeCandidateFitAnalysis:
  candidate_id: str
  publication_number: str = ""
  theme_fit: float = 0.0
  material_fit: float = 0.0
  process_fit: float = 0.0
  property_fit: float = 0.0
  claim_relevance: float = 0.0
  assignee_signal: float = 0.0
  recency: float = 0.0
  source_quality: float = 0.0
  noise_penalty: float = 0.0
  matched_theme_keywords: list[str] = field(default_factory=list)
  matched_material_keywords: list[str] = field(default_factory=list)
  matched_process_keywords: list[str] = field(default_factory=list)
  matched_property_keywords: list[str] = field(default_factory=list)
  matched_exclude_keywords: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class Top5ReadingGuide:
  publication_number: str
  title: str = ""
  why_read: str = ""
  theme_relationship: str = ""
  technical_elements: list[str] = field(default_factory=list)
  claim_map_focus: str = ""
  evidence_map_focus: str = ""
  examples_focus: str = ""
  positive_reasons: list[str] = field(default_factory=list)
  negative_reasons: list[str] = field(default_factory=list)
  why_selected_over_others: str = ""
  next_reading_question: str = ""
  narrative: str = ""
  caution: str = "スコアは読む優先度であり、法的価値・権利範囲評価ではありません。"

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class DroppedFromTop5Example:
  publication_number: str
  title: str = ""
  heuristic_score: float = 0.0
  drop_category: str = ""
  drop_reason: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class DroppedFromTop5Summary:
  dropped_count: int = 0
  category_counts: dict[str, int] = field(default_factory=dict)
  representative_examples: list[DroppedFromTop5Example] = field(default_factory=list)
  summary_text: str = ""

  def to_dict(self) -> dict[str, Any]:
    return {
      "dropped_count": self.dropped_count,
      "category_counts": dict(self.category_counts),
      "representative_examples": [e.to_dict() for e in self.representative_examples],
      "summary_text": self.summary_text,
    }


@dataclass
class ThemeBasedRankingPolicy:
  case_id: str
  theme_name: str = ""
  theme_description: str = ""
  triage_engine: str = ""
  ranking_policy_id: str = "theme_based_reading_priority_v1"
  weights: list[ThemeRankingWeight] = field(default_factory=list)
  safety_notices: list[str] = field(default_factory=lambda: list(THEME_RANKING_SAFETY_NOTICES))

  def to_dict(self) -> dict[str, Any]:
    return {
      "case_id": self.case_id,
      "theme_name": self.theme_name,
      "theme_description": self.theme_description,
      "triage_engine": self.triage_engine,
      "ranking_policy_id": self.ranking_policy_id,
      "weights": [w.to_dict() for w in self.weights],
      "safety_notices": list(self.safety_notices),
    }
