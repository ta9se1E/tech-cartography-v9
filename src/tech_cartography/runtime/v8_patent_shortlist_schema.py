"""v8 Patent Shortlist schema (Phase 27D)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tech_cartography.runtime.v8_sources_schema import utc_now_iso

SHORTLIST_SAFETY_NOTICES: tuple[str, ...] = (
  "total_score は読む優先度の暫定スコア（heuristic / draft selection）であり、"
  "特許価値・権利価値・有効性・侵害リスクを意味しません。",
  "FTO、侵害、有効性判断、法的結論は行いません。",
  "claim text not loaded — 請求項・明細書は未読です。原典公報で人手確認してください。",
  "candidate information only — Web Signal 由来の情報は候補扱いです。",
  "manually_verified / human_verified は自動付与しません。",
)

NEXT_PHASE_CONNECTIONS: tuple[str, ...] = (
  "Claim Map — 請求項を技術軸で分解する（Phase27E）",
  "Evidence Map — 実施例・論文と対応付ける（Phase27F）",
  "Gap / Next Actions — 裏取り不足と次の確認（Phase27G/H）",
  "定点観測 — Top特許の変化を次回 Digest / Scheduler で追跡",
)


@dataclass
class V8PatentCandidate:
  candidate_id: str
  case_id: str
  rank: int
  publication_number: str
  title: str
  assignee_or_organization: str = ""
  year: str = ""
  url: str = ""
  source_id: str = ""
  source_status: str = ""
  evidence_role: str = ""
  related_claim_axes: list[str] = field(default_factory=list)
  technical_axis_labels: list[str] = field(default_factory=list)
  theme_fit_score: float = 0.0
  evidence_potential_score: float = 0.0
  claim_specificity_score: float = 0.0
  recency_score: float = 0.0
  strategic_relevance_score: float = 0.0
  manual_review_priority_score: float = 0.0
  total_score: float = 0.0
  score_breakdown: dict[str, float] = field(default_factory=dict)
  why_read: str = ""
  key_claim_focus: str = ""
  expected_evidence_to_check: str = ""
  evidence_gap_hypothesis: str = ""
  next_verification_action: str = ""
  next_phase: str = "Claim Map"
  caution_flags: list[str] = field(default_factory=list)
  candidate_information_only: bool = False
  human_review_required: bool = False
  no_legal_judgement: bool = True
  created_at: str = field(default_factory=utc_now_iso)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> V8PatentCandidate:
    known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    filtered = {key: data[key] for key in known if key in data}
    for list_key in ("related_claim_axes", "technical_axis_labels", "caution_flags"):
      if list_key not in filtered:
        filtered[list_key] = []
    if "score_breakdown" not in filtered:
      filtered["score_breakdown"] = {}
    return cls(**filtered)


@dataclass
class V8PatentShortlist:
  case_id: str
  case_name: str
  top_n: int
  count: int
  patent_candidates: list[V8PatentCandidate] = field(default_factory=list)
  excluded_sources: list[str] = field(default_factory=list)
  warnings: list[str] = field(default_factory=list)
  generated_at: str = field(default_factory=utc_now_iso)

  def to_dict(self) -> dict[str, Any]:
    return {
      "case_id": self.case_id,
      "case_name": self.case_name,
      "top_n": self.top_n,
      "count": self.count,
      "patent_candidates": [c.to_dict() for c in self.patent_candidates],
      "excluded_sources": self.excluded_sources,
      "warnings": self.warnings,
      "generated_at": self.generated_at,
    }


@dataclass
class V8PatentShortlistExport:
  case_id: str
  case_name: str
  generated_at: str
  top_n: int
  output_dir: str
  csv_path: str
  md_path: str
  xlsx_path: str
  manifest_path: str
  excel_warning: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)
