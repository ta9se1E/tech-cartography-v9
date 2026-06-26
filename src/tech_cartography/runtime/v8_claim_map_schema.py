"""v8 Claim Map schema (Phase 27E)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tech_cartography.runtime.v8_sources_schema import utc_now_iso

CLAIM_MAP_SAFETY_NOTICES: tuple[str, ...] = (
  "Claim Map は請求項を技術軸へ整理する暫定分類（heuristic / draft）であり、"
  "権利範囲の解釈・特許価値・侵害・有効性判断ではありません。",
  "FTO、侵害、有効性判断、法的結論は行いません。",
  "claim text not loaded — 請求項本文が未取得の場合は分類を行いません。原典公報で人手確認してください。",
  "candidate information only — Web Signal 由来の情報は候補扱いです。",
  "manually_verified / human_verified は自動付与しません。",
)

CLAIM_MAP_NEXT_PHASES: tuple[str, ...] = (
  "Evidence Map — 実施例・論文・Web情報と対応付ける（Phase27F）",
  "Gap / Next Actions — 裏取り不足と次の確認（Phase27G/H）",
  "定点観測 — Claim Map 軸の変化を次回 Digest / Scheduler で追跡",
)

VALID_CLAIM_TEXT_STATUSES: tuple[str, ...] = (
  "loaded",
  "not_loaded",
  "manual_input",
  "csv_imported",
  "artifact_imported",
)

VALID_EVIDENCE_PRIORITIES: tuple[str, ...] = ("high", "medium", "low", "unknown")


@dataclass
class V8ClaimRecord:
  claim_id: str
  case_id: str
  publication_number: str
  patent_title: str
  claim_no: str
  claim_text: str
  claim_text_status: str = "not_loaded"
  claim_source_type: str = "unavailable"
  claim_source_path: str = ""
  claim_source_url: str = ""
  technical_axis_labels: list[str] = field(default_factory=list)
  primary_axis: str = "unknown"
  material_terms: list[str] = field(default_factory=list)
  process_terms: list[str] = field(default_factory=list)
  property_terms: list[str] = field(default_factory=list)
  structure_terms: list[str] = field(default_factory=list)
  application_terms: list[str] = field(default_factory=list)
  condition_terms: list[str] = field(default_factory=list)
  evidence_needed: list[str] = field(default_factory=list)
  evidence_priority: str = "unknown"
  why_this_claim_matters: str = ""
  next_evidence_check: str = ""
  next_phase: str = "Evidence Map"
  caution_flags: list[str] = field(default_factory=list)
  candidate_information_only: bool = False
  human_review_required: bool = True
  no_legal_judgement: bool = True
  created_at: str = field(default_factory=utc_now_iso)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> V8ClaimRecord:
    known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    filtered = {key: data[key] for key in known if key in data}
    for list_key in (
      "technical_axis_labels",
      "material_terms",
      "process_terms",
      "property_terms",
      "structure_terms",
      "application_terms",
      "condition_terms",
      "evidence_needed",
      "caution_flags",
    ):
      if list_key not in filtered:
        filtered[list_key] = []
    return cls(**filtered)


@dataclass
class V8ClaimMap:
  claim_map_id: str
  case_id: str
  publication_number: str
  generated_at: str
  records: list[V8ClaimRecord] = field(default_factory=list)
  claim_count: int = 0
  loaded_claim_count: int = 0
  not_loaded_claim_count: int = 0
  count_by_axis: dict[str, int] = field(default_factory=dict)
  count_by_evidence_needed: dict[str, int] = field(default_factory=dict)
  warnings: list[str] = field(default_factory=list)
  source_artifact_paths: list[str] = field(default_factory=list)
  next_actions: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return {
      "claim_map_id": self.claim_map_id,
      "case_id": self.case_id,
      "publication_number": self.publication_number,
      "generated_at": self.generated_at,
      "records": [r.to_dict() for r in self.records],
      "claim_count": self.claim_count,
      "loaded_claim_count": self.loaded_claim_count,
      "not_loaded_claim_count": self.not_loaded_claim_count,
      "count_by_axis": self.count_by_axis,
      "count_by_evidence_needed": self.count_by_evidence_needed,
      "warnings": self.warnings,
      "source_artifact_paths": self.source_artifact_paths,
      "next_actions": self.next_actions,
    }


@dataclass
class V8ClaimMapExport:
  case_id: str
  publication_number: str
  generated_at: str
  output_dir: str
  csv_path: str
  md_path: str
  xlsx_path: str
  manifest_path: str
  excel_warning: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)
