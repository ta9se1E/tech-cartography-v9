"""Example facts extraction schema (Phase 27S.3)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

EXAMPLE_FACTS_NOTICES: tuple[str, ...] = (
  "抽出結果は候補であり、needs_human_review=True が基本です。",
  "Evidenceは証明ではなく裏取り候補、Gapは弱点ではなく未確認事項です。",
  "Geminiは明示ボタン操作時のみ実行します（ENABLE_GEMINI_EXAMPLE_FACTS=false がデフォルト）。",
  "権利範囲・侵害・FTO・有効性判断は行いません。",
)

VALID_FACT_TYPES: tuple[str, ...] = (
  "material",
  "process_condition",
  "property_value",
  "property_candidate",
  "structure_property",
  "comparison_example",
  "comparison_candidate",
  "table_value",
  "table_candidate",
  "structure_characterization",
  "example_overview",
  "unknown",
)

VALID_FACT_STATUSES: tuple[str, ...] = (
  "ok",
  "prompts_only",
  "gemini_disabled",
  "gemini_error",
  "no_target_sections",
  "empty",
)


@dataclass
class ExampleFact:
  case_id: str
  publication_number: str
  section_id: str
  section_type: str
  fact_id: str
  evidence_text: str
  fact_type: str = "unknown"
  example_id: str | None = None
  example_label: str | None = None
  material: str | None = None
  process_step: str | None = None
  condition_name: str | None = None
  condition_value: str | None = None
  condition_unit: str | None = None
  property_name: str | None = None
  property_value: str | None = None
  property_unit: str | None = None
  comparison_type: str | None = None
  comparison_target: str | None = None
  table_id: str | None = None
  matched_user_keywords: list[str] = field(default_factory=list)
  page_start: int | None = None
  page_end: int | None = None
  confidence: float = 0.5
  needs_human_review: bool = True
  extraction_method: str = "gemini"
  warning: str | None = None

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class ExampleFactsExtractionResult:
  case_id: str
  publication_number: str
  source_sections_csv: str | None = None
  target_section_count: int = 0
  fact_count: int = 0
  example_count: int = 0
  comparative_example_count: int = 0
  property_fact_count: int = 0
  process_condition_fact_count: int = 0
  structure_property_fact_count: int = 0
  table_candidate_count: int = 0
  comparison_candidate_count: int = 0
  property_candidate_count: int = 0
  unknown_fact_count: int = 0
  matched_user_keyword_count: int = 0
  needs_human_review: bool = True
  facts: list[ExampleFact] = field(default_factory=list)
  output_dir: str | None = None
  status: str = "ok"
  warning: str | None = None

  def to_dict(self) -> dict[str, Any]:
    return {
      "case_id": self.case_id,
      "publication_number": self.publication_number,
      "source_sections_csv": self.source_sections_csv,
      "target_section_count": self.target_section_count,
      "fact_count": self.fact_count,
      "example_count": self.example_count,
      "comparative_example_count": self.comparative_example_count,
      "property_fact_count": self.property_fact_count,
      "process_condition_fact_count": self.process_condition_fact_count,
      "structure_property_fact_count": self.structure_property_fact_count,
      "table_candidate_count": self.table_candidate_count,
      "comparison_candidate_count": self.comparison_candidate_count,
      "property_candidate_count": self.property_candidate_count,
      "unknown_fact_count": self.unknown_fact_count,
      "matched_user_keyword_count": self.matched_user_keyword_count,
      "needs_human_review": self.needs_human_review,
      "facts": [f.to_dict() for f in self.facts],
      "output_dir": self.output_dir,
      "status": self.status,
      "warning": self.warning,
    }
