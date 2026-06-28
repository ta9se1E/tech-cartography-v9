"""Extraction focus vocabulary schema (Phase 27S.3)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

VOCABULARY_NOTICES: tuple[str, ...] = (
  "抽出語彙はヒントであり、本文に明示された内容のみを抽出対象とします。",
  "語彙にない重要ファクトでも、本文に明示されていれば抽出候補になります。",
  "語彙にあるだけでファクトを生成しません。",
)

VOCABULARY_CATEGORIES: tuple[str, ...] = (
  "material_keywords",
  "process_keywords",
  "property_keywords",
  "structure_keywords",
  "comparison_keywords",
  "table_keywords",
  "exclusion_keywords",
)


@dataclass
class ExtractionVocabulary:
  case_id: str
  theme_name: str | None = None
  theme_description: str | None = None
  material_keywords: list[str] = field(default_factory=list)
  process_keywords: list[str] = field(default_factory=list)
  property_keywords: list[str] = field(default_factory=list)
  structure_keywords: list[str] = field(default_factory=list)
  comparison_keywords: list[str] = field(default_factory=list)
  table_keywords: list[str] = field(default_factory=list)
  exclusion_keywords: list[str] = field(default_factory=list)
  user_notes: str | None = None
  updated_at: str | None = None
  source: str = "default"

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> ExtractionVocabulary:
    return cls(
      case_id=str(data.get("case_id", "")),
      theme_name=data.get("theme_name"),
      theme_description=data.get("theme_description"),
      material_keywords=list(data.get("material_keywords") or []),
      process_keywords=list(data.get("process_keywords") or []),
      property_keywords=list(data.get("property_keywords") or []),
      structure_keywords=list(data.get("structure_keywords") or []),
      comparison_keywords=list(data.get("comparison_keywords") or []),
      table_keywords=list(data.get("table_keywords") or []),
      exclusion_keywords=list(data.get("exclusion_keywords") or []),
      user_notes=data.get("user_notes"),
      updated_at=data.get("updated_at"),
      source=str(data.get("source") or "user"),
    )

  def keyword_counts(self) -> dict[str, int]:
    return {
      "material": len(self.material_keywords),
      "process": len(self.process_keywords),
      "property": len(self.property_keywords),
      "structure": len(self.structure_keywords),
      "comparison": len(self.comparison_keywords),
      "table": len(self.table_keywords),
      "exclusion": len(self.exclusion_keywords),
    }

  def all_keywords(self) -> list[str]:
    combined: list[str] = []
    for cat in VOCABULARY_CATEGORIES:
      combined.extend(getattr(self, cat))
    return combined
