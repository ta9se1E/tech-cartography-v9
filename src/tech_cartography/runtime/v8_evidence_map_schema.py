"""v8 Evidence Map schema (Phase 27F)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tech_cartography.runtime.v8_sources_schema import utc_now_iso

EVIDENCE_MAP_SAFETY_NOTICES: tuple[str, ...] = (
  "Evidence Map は claim / source の裏付け候補対応表（supporting evidence candidate）であり、"
  "証明・確定Evidenceではありません。",
  "Evidence Map is not proof — direct support と断定しません。",
  "paper / web / company source は supporting evidence candidate です。一次情報の人手確認が必要です。",
  "claim text not loaded — claim_text_required として未確認扱いです。",
  "FTO、侵害、有効性判断、法的結論は行いません。",
  "manually_verified / human_verified は自動付与しません。",
)

EVIDENCE_MAP_NEXT_PHASES: tuple[str, ...] = (
  "Gap / Next Actions — 不足 Evidence を整理（Phase27G/H）",
  "定点観測 — Evidence Gap 変化を次回 Digest / Scheduler で追跡",
  "Watch Profile 更新 — paper 不足時は論文検索範囲拡大候補",
)


@dataclass
class V8EvidenceLink:
  evidence_link_id: str
  case_id: str
  publication_number: str
  patent_title: str
  claim_id: str
  claim_no: str
  claim_text_status: str
  primary_axis: str
  technical_axis_labels: list[str] = field(default_factory=list)
  evidence_needed: list[str] = field(default_factory=list)
  source_id: str = ""
  source_type: str = "unknown"
  source_title: str = ""
  source_organization: str = ""
  source_year: str = ""
  source_url: str = ""
  publication_number_or_doi: str = ""
  evidence_role: str = "unknown"
  support_type: str = "unknown"
  support_level: str = "not_assessed"
  match_reason: str = ""
  matched_terms: list[str] = field(default_factory=list)
  evidence_gap: str = ""
  next_verification_action: str = ""
  verification_status: str = "unverified"
  candidate_information_only: bool = False
  human_review_required: bool = True
  no_legal_judgement: bool = True
  caution_flags: list[str] = field(default_factory=list)
  source_artifact_paths: list[str] = field(default_factory=list)
  created_at: str = field(default_factory=utc_now_iso)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> V8EvidenceLink:
    known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    filtered = {key: data[key] for key in known if key in data}
    for list_key in (
      "technical_axis_labels",
      "evidence_needed",
      "matched_terms",
      "caution_flags",
      "source_artifact_paths",
    ):
      if list_key not in filtered:
        filtered[list_key] = []
    return cls(**filtered)


@dataclass
class V8EvidenceMap:
  evidence_map_id: str
  case_id: str
  publication_number: str
  generated_at: str
  links: list[V8EvidenceLink] = field(default_factory=list)
  link_count: int = 0
  claim_count: int = 0
  source_count: int = 0
  count_by_support_type: dict[str, int] = field(default_factory=dict)
  count_by_support_level: dict[str, int] = field(default_factory=dict)
  count_by_source_type: dict[str, int] = field(default_factory=dict)
  missing_evidence_count: int = 0
  claim_text_required_count: int = 0
  warnings: list[str] = field(default_factory=list)
  source_artifact_paths: list[str] = field(default_factory=list)
  next_actions: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return {
      "evidence_map_id": self.evidence_map_id,
      "case_id": self.case_id,
      "publication_number": self.publication_number,
      "generated_at": self.generated_at,
      "links": [link.to_dict() for link in self.links],
      "link_count": self.link_count,
      "claim_count": self.claim_count,
      "source_count": self.source_count,
      "count_by_support_type": self.count_by_support_type,
      "count_by_support_level": self.count_by_support_level,
      "count_by_source_type": self.count_by_source_type,
      "missing_evidence_count": self.missing_evidence_count,
      "claim_text_required_count": self.claim_text_required_count,
      "warnings": self.warnings,
      "source_artifact_paths": self.source_artifact_paths,
      "next_actions": self.next_actions,
    }


@dataclass
class V8EvidenceMapExport:
  export_id: str
  case_id: str
  publication_number: str
  output_dir: str
  csv_path: str
  md_path: str
  xlsx_path: str
  manifest_path: str
  created_at: str
  excel_warning: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)
