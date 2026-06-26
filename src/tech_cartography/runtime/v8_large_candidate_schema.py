"""v8 Large Candidate schema (Phase 27J.0)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tech_cartography.runtime.v8_sources_schema import utc_now_iso

LARGE_CANDIDATE_SAFETY_NOTICES: tuple[str, ...] = (
  "1000件候補は母集団であり、全件を Claim Map / Evidence Map で深掘りしません。",
  "Top100 / Top20 / Top5 の段階選抜後、Top5 またはユーザー選択のみ深掘り対象です。",
  "heuristic_score は読む優先度の暫定値であり、技術的正しさ・特許価値・法的価値ではありません。",
  "FTO、侵害、有効性判断、法的結論は行いません。",
  "重複除去は暫定 heuristic です。family_id や title 類似だけで同一特許と断定しません。",
  "本 Phase では外部 API / BigQuery 実行 / メール送信 / Scheduler 起動を行いません。",
)

VALID_STAGE_LABELS: tuple[str, ...] = (
  "population",
  "deduped",
  "scored",
  "top100",
  "top20",
  "top5",
  "excluded",
)

VALID_SOURCE_TYPES: tuple[str, ...] = (
  "patent",
  "paper",
  "web",
  "company",
  "unknown",
)

CASE_KEYWORDS: dict[str, tuple[str, ...]] = {
  "case_01_pan_graphitization": (
    "pan", "polyacrylonitrile", "precursor", "stabilization", "oxidation",
    "carbonization", "graphitization", "tensile", "modulus", "carbon fiber", "fiber bundle",
  ),
  "case_02_sizing_interface": (
    "sizing", "surface treatment", "coating", "interface", "interfacial", "adhesion",
    "matrix", "resin", "epoxy", "composite", "ilss", "shear strength",
  ),
  "case_03_pressure_vessel_filament_winding": (
    "pressure vessel", "hydrogen tank", "filament winding", "cfrp", "composite pressure vessel",
    "liner", "type iv", "burst", "fatigue", "hoop", "winding", "towpreg",
  ),
}


@dataclass
class V8LargeCandidateQualityIssue:
  issue_id: str
  case_id: str
  candidate_id: str
  issue_type: str
  severity: str
  message: str
  publication_number: str = ""
  raw_row_number: int = 0

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class V8LargeCandidateRecord:
  candidate_id: str
  case_id: str
  source_type: str = "patent"
  publication_number: str = ""
  family_id: str = ""
  title: str = ""
  abstract: str = ""
  organization: str = ""
  assignee: str = ""
  inventors: str = ""
  country_code: str = ""
  kind_code: str = ""
  publication_date: str = ""
  year: str = ""
  url: str = ""
  source_url: str = ""
  source_status: str = "candidate"
  evidence_role: str = "claim_source"
  reliability_label: str = "unverified"
  verification_status: str = "unverified"
  candidate_information_only: bool = True
  human_review_required: bool = True
  raw_source_file: str = ""
  raw_row_number: int = 0
  normalized_title: str = ""
  normalized_publication_number: str = ""
  dedupe_key: str = ""
  is_duplicate: bool = False
  duplicate_of: str = ""
  keyword_match_count: int = 0
  matched_keywords: list[str] = field(default_factory=list)
  heuristic_score: float = 0.0
  score_reason: str = ""
  next_verification_action: str = ""
  rank: int = 0
  positive_reasons: list[str] = field(default_factory=list)
  negative_reasons: list[str] = field(default_factory=list)
  ranking_policy: str = ""
  selected_stage: str = ""
  why_selected: str = ""
  stage_label: str = "population"
  exclusion_reason: str = ""
  created_at: str = field(default_factory=utc_now_iso)

  def to_dict(self) -> dict[str, Any]:
    d = asdict(self)
    d["matched_keywords"] = list(self.matched_keywords)
    d["positive_reasons"] = list(self.positive_reasons)
    d["negative_reasons"] = list(self.negative_reasons)
    return d

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> V8LargeCandidateRecord:
    known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    filtered = {k: data[k] for k in known if k in data}
    if "matched_keywords" not in filtered:
      filtered["matched_keywords"] = []
    for list_key in ("positive_reasons", "negative_reasons"):
      if list_key not in filtered:
        val = data.get(list_key)
        if isinstance(val, str) and val:
          filtered[list_key] = [k for k in val.split("|") if k]
        else:
          filtered[list_key] = []
    if "rank" in filtered:
      try:
        filtered["rank"] = int(filtered.get("rank") or 0)
      except (TypeError, ValueError):
        filtered["rank"] = 0
    return cls(**filtered)


@dataclass
class V8LargeCandidateImportResult:
  import_id: str
  case_id: str
  input_path: str
  imported_at: str
  input_row_count: int = 0
  accepted_row_count: int = 0
  rejected_row_count: int = 0
  max_rows_applied: int = 1000
  output_candidates_path: str = ""
  output_profile_path: str = ""
  warnings: list[str] = field(default_factory=list)
  quality_issues: list[dict[str, Any]] = field(default_factory=list)
  no_external_api: bool = True
  no_bigquery_execution: bool = True
  no_email_send: bool = True
  no_scheduler_start: bool = True

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class V8LargeCandidatePopulationProfile:
  profile_id: str
  case_id: str
  generated_at: str
  total_candidates: int = 0
  patent_count: int = 0
  paper_count: int = 0
  web_count: int = 0
  company_count: int = 0
  unknown_count: int = 0
  unique_publication_count: int = 0
  duplicate_count: int = 0
  missing_title_count: int = 0
  missing_publication_number_count: int = 0
  missing_url_count: int = 0
  year_min: str = ""
  year_max: str = ""
  count_by_year: dict[str, int] = field(default_factory=dict)
  count_by_organization: dict[str, int] = field(default_factory=dict)
  count_by_country: dict[str, int] = field(default_factory=dict)
  count_by_source_type: dict[str, int] = field(default_factory=dict)
  count_by_stage_label: dict[str, int] = field(default_factory=dict)
  warnings: list[str] = field(default_factory=list)
  candidate_information_only: bool = True
  human_review_required: bool = True
  no_legal_judgement: bool = True

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class V8LargeCandidateStageSelection:
  selection_id: str
  case_id: str
  generated_at: str
  population_count: int = 0
  deduped_count: int = 0
  scored_count: int = 0
  top100_count: int = 0
  top20_count: int = 0
  top5_count: int = 0
  top100_path: str = ""
  top20_path: str = ""
  top5_path: str = ""
  scoring_policy: str = "keyword_heuristic_v1"
  ranking_policy: str = ""
  triage_engine: str = ""
  selection_summary: str = ""
  warnings: list[str] = field(default_factory=list)
  candidate_information_only: bool = True
  no_legal_judgement: bool = True

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class V8LargeCandidateShortlistPack:
  pack_id: str
  case_id: str
  generated_at: str
  selection: V8LargeCandidateStageSelection
  population_path: str = ""
  deduped_path: str = ""
  scored_path: str = ""
  summary_path: str = ""
  manifest_path: str = ""
  output_dir: str = ""
  warnings: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return {
      "pack_id": self.pack_id,
      "case_id": self.case_id,
      "generated_at": self.generated_at,
      "selection": self.selection.to_dict(),
      "population_path": self.population_path,
      "deduped_path": self.deduped_path,
      "scored_path": self.scored_path,
      "summary_path": self.summary_path,
      "manifest_path": self.manifest_path,
      "output_dir": self.output_dir,
      "warnings": self.warnings,
    }


@dataclass
class V8LargeCandidateExport:
  export_id: str
  output_dir: str
  manifest_path: str
  created_at: str

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)
