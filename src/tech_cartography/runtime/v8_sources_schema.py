"""Unified v8 Sources schema (Phase 27C)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

SOURCE_TYPES: tuple[str, ...] = (
  "patent",
  "paper",
  "web",
  "company",
  "pdf",
  "csv",
  "manual",
  "unknown",
)

SOURCE_STATUSES: tuple[str, ...] = (
  "primary_candidate",
  "supporting_candidate",
  "weak_signal",
  "uploaded",
  "manual_review_required",
  "excluded",
  "verified_primary",
  "candidate",
  "candidate_information_only",
)

EVIDENCE_ROLES: tuple[str, ...] = (
  "claim_source",
  "example_source",
  "paper_evidence",
  "web_signal",
  "company_signal",
  "market_signal",
  "background",
  "process_claim_support",
  "process_property",
  "interface_claim",
  "interface_evidence",
  "safety_claim",
  "safety_evidence",
  "background_context",
  "claim_support",
  "unknown",
)

RELIABILITY_LABELS: tuple[str, ...] = (
  "primary",
  "secondary",
  "candidate",
  "weak",
  "unknown",
)

VERIFICATION_STATUSES: tuple[str, ...] = (
  "unverified",
  "needs_human_review",
  "source_url_available",
  "manually_verified",
)

SAFETY_EXPORT_NOTICES: tuple[str, ...] = (
  "候補情報（candidate information only）であり確定事実ではありません。",
  "human review required の行は一次情報の人手確認が必要です。",
  "FTO、侵害、有効性判断、法的結論は行いません。",
  "Web / company source は定点観測・メール Digest の候補シグナルとして扱い、Claim 根拠に断定しません。",
  "manually_verified / human_verified は自動付与しません。",
)

FIXED_POINT_OBSERVATION_NOTE = (
  "この Sources 一覧は、次回 Watch Profile 更新・Scheduler 定点観測・メール Digest に"
  "引き継ぐ基礎データです。メール送信と Scheduler は必須機能として保持します（デフォルト OFF）。"
)

NEXT_PHASE_PLACEHOLDERS: tuple[str, ...] = (
  "Patent Shortlist — Phase27D",
  "Claim Map — Phase27E",
  "Evidence Map — Phase27F",
  "Gap / Next Actions — Phase27G/H",
)


def utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class V8SourceRecord:
  source_id: str
  case_id: str
  source_type: str
  title: str
  organization: str = ""
  year: str = ""
  url: str = ""
  publication_number: str = ""
  doi: str = ""
  source_status: str = "candidate"
  evidence_role: str = "unknown"
  reliability_label: str = "unknown"
  verification_status: str = "unverified"
  candidate_information_only: bool = False
  human_review_required: bool = False
  related_claim_axes: list[str] = field(default_factory=list)
  related_case_theme: str = ""
  source_file_path: str = ""
  artifact_path: str = ""
  notes: str = ""
  created_at: str = field(default_factory=utc_now_iso)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> V8SourceRecord:
    known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    filtered = {key: data[key] for key in known if key in data}
    if "related_claim_axes" not in filtered:
      filtered["related_claim_axes"] = []
    return cls(**filtered)


@dataclass
class V8SourcesTable:
  records: list[V8SourceRecord] = field(default_factory=list)
  source_count: int = 0
  count_by_case: dict[str, int] = field(default_factory=dict)
  count_by_type: dict[str, int] = field(default_factory=dict)
  count_by_evidence_role: dict[str, int] = field(default_factory=dict)
  warnings: list[str] = field(default_factory=list)
  excluded_or_duplicate_count: int = 0
  loaded_at: str = field(default_factory=utc_now_iso)

  def to_dict(self) -> dict[str, Any]:
    return {
      "records": [record.to_dict() for record in self.records],
      "source_count": self.source_count,
      "count_by_case": self.count_by_case,
      "count_by_type": self.count_by_type,
      "count_by_evidence_role": self.count_by_evidence_role,
      "warnings": self.warnings,
      "excluded_or_duplicate_count": self.excluded_or_duplicate_count,
      "loaded_at": self.loaded_at,
    }


@dataclass
class V8SourceExportPackage:
  case_id: str
  case_name: str
  generated_at: str
  source_count: int
  count_by_type: dict[str, int]
  count_by_evidence_role: dict[str, int]
  warnings: list[str]
  output_dir: str
  manifest_path: str
  sources_csv_path: str
  sources_md_path: str
  sources_xlsx_path: str
  export_summary_path: str
  excel_warning: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)
