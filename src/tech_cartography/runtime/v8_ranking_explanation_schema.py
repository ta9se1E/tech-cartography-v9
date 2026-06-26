"""v8 Ranking Explanation schema (Phase 27J.1)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tech_cartography.runtime.v8_sources_schema import utc_now_iso

RANKING_EXPLANATION_NOTICES: tuple[str, ...] = (
  "ranking explanation は読む優先度の説明であり、技術的正しさ・特許価値・法的価値ではありません。",
  "FTO、侵害、有効性判断、法的結論は行いません。",
  "1000件母集団の全件を Deep Dive しません。Claim Map / Evidence Map は Top5 またはユーザー選択に限定します。",
  "heuristic_score / score contribution は暫定 heuristic です。",
)

VALID_CONTRIBUTION_FACTORS: tuple[str, ...] = (
  "include_term_hit",
  "target_company_hit",
  "us_publication",
  "publication_number_present",
  "title_present",
  "abstract_present",
  "new_assignee",
  "exclude_term_hit",
  "quality_penalty",
  "duplicate_penalty",
  "fallback_heuristic",
  "unknown",
)


@dataclass
class V8ScoreContribution:
  contribution_id: str
  factor_name: str
  matched_value: str = ""
  score_delta: float = 0.0
  reason: str = ""
  evidence_field: str = ""
  candidate_information_only: bool = True

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class V8CandidateRankingExplanation:
  candidate_id: str
  case_id: str
  publication_number: str = ""
  title: str = ""
  organization: str = ""
  assignee: str = ""
  year: str = ""
  country_code: str = ""
  stage_label: str = ""
  heuristic_score: float = 0.0
  rank_in_population: int = 0
  rank_in_deduped: int = 0
  rank_in_scored: int = 0
  rank_in_top100: int = 0
  rank_in_top20: int = 0
  rank_in_top5: int = 0
  selected_for_top100: bool = False
  selected_for_top20: bool = False
  selected_for_top5: bool = False
  selected_for_deep_dive: bool = False
  score_contributions: list[V8ScoreContribution] = field(default_factory=list)
  positive_reasons: list[str] = field(default_factory=list)
  negative_reasons: list[str] = field(default_factory=list)
  why_selected: str = ""
  why_not_selected: str = ""
  next_verification_action: str = ""
  ranking_policy: str = ""
  candidate_information_only: bool = True
  human_review_required: bool = True
  no_legal_judgement: bool = True
  caution_flags: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    d = asdict(self)
    d["score_contributions"] = [c.to_dict() for c in self.score_contributions]
    return d


@dataclass
class V8StageRankingExplanation:
  stage_name: str
  input_count: int = 0
  output_count: int = 0
  selection_rule: str = ""
  main_positive_factors: list[str] = field(default_factory=list)
  main_negative_factors: list[str] = field(default_factory=list)
  warnings: list[str] = field(default_factory=list)
  no_legal_judgement: bool = True

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class V8RankingExplanationReport:
  report_id: str
  case_id: str
  generated_at: str
  ranking_policy: str = ""
  triage_engine: str = "fallback_large_candidate_heuristic"
  population_count: int = 0
  deduped_count: int = 0
  scored_count: int = 0
  top100_count: int = 0
  top20_count: int = 0
  top5_count: int = 0
  stage_explanations: list[V8StageRankingExplanation] = field(default_factory=list)
  candidate_explanations: list[V8CandidateRankingExplanation] = field(default_factory=list)
  top5_summary: str = ""
  dropped_candidate_summary: str = ""
  common_selection_reasons: list[str] = field(default_factory=list)
  common_exclusion_reasons: list[str] = field(default_factory=list)
  warnings: list[str] = field(default_factory=list)
  candidate_information_only: bool = True
  no_legal_judgement: bool = True
  no_deep_dive_all_population: bool = True

  def to_dict(self) -> dict[str, Any]:
    return {
      "report_id": self.report_id,
      "case_id": self.case_id,
      "generated_at": self.generated_at,
      "ranking_policy": self.ranking_policy,
      "triage_engine": self.triage_engine,
      "population_count": self.population_count,
      "deduped_count": self.deduped_count,
      "scored_count": self.scored_count,
      "top100_count": self.top100_count,
      "top20_count": self.top20_count,
      "top5_count": self.top5_count,
      "stage_explanations": [s.to_dict() for s in self.stage_explanations],
      "candidate_explanations": [c.to_dict() for c in self.candidate_explanations],
      "top5_summary": self.top5_summary,
      "dropped_candidate_summary": self.dropped_candidate_summary,
      "common_selection_reasons": self.common_selection_reasons,
      "common_exclusion_reasons": self.common_exclusion_reasons,
      "warnings": self.warnings,
      "candidate_information_only": self.candidate_information_only,
      "no_legal_judgement": self.no_legal_judgement,
      "no_deep_dive_all_population": self.no_deep_dive_all_population,
    }


@dataclass
class V8RankingExplanationExport:
  export_id: str
  case_id: str
  output_dir: str
  json_path: str = ""
  md_path: str = ""
  csv_path: str = ""
  top5_md_path: str = ""
  dropped_md_path: str = ""
  created_at: str = field(default_factory=utc_now_iso)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)
