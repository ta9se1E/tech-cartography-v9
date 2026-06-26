"""v8 One Case Real Demo E2E schema (Phase 27N.5)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tech_cartography.runtime.v8_sources_schema import utc_now_iso

ONE_CASE_DEMO_SAFETY_NOTICES: tuple[str, ...] = (
  "claim 本文はユーザー提供のみ — システムは自動生成しません。",
  "fixture を本物の1000件 CSV として扱いません。",
  "1000件は母集団 — Top5 のみ Deep Dive 対象。",
  "Cloud Build / Cloud Run deploy / 外部 API / メール / Scheduler はこの Phase では実行しません。",
  "FTO、侵害、有効性判断、法的結論は行いません。",
)

DEFAULT_ONE_CASE_ID = "case_01_pan_graphitization"
DEFAULT_ONE_CASE_INPUT_CSV = (
  "cases/case_01_pan_graphitization/large_candidates/case_01_bigquery_export_1000.csv"
)


@dataclass
class V8OneCaseDemoStepStatus:
  step_id: str
  step_name: str
  status: str
  summary: str = ""
  next_user_action: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class V8OneCaseDemoSummary:
  case_id: str
  generated_at: str
  input_csv_path: str
  input_csv_exists: bool = False
  imported_count: int | None = None
  deduped_count: int | None = None
  top100_count: int | None = None
  top20_count: int | None = None
  top5_count: int | None = None
  top5_publication_numbers: list[str] = field(default_factory=list)
  manual_claim_count: int = 0
  claim_text_required_count: int = 0
  evidence_link_count: int | None = None
  gap_count: int | None = None
  demo_polish_pack_path: str = ""
  demo_readiness_status: str = ""
  overall_status: str = "needs_input_csv"
  next_user_action: str = ""
  step_statuses: list[V8OneCaseDemoStepStatus] = field(default_factory=list)
  output_dir: str = ""
  manifest_path: str = ""
  no_claim_text_generated: bool = True
  no_cloud_build: bool = True
  no_cloud_run_deploy: bool = True
  no_email_send: bool = True
  no_scheduler_start: bool = True
  warnings: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return {
      "case_id": self.case_id,
      "generated_at": self.generated_at,
      "input_csv_path": self.input_csv_path,
      "input_csv_exists": self.input_csv_exists,
      "imported_count": self.imported_count,
      "deduped_count": self.deduped_count,
      "top100_count": self.top100_count,
      "top20_count": self.top20_count,
      "top5_count": self.top5_count,
      "top5_publication_numbers": self.top5_publication_numbers,
      "manual_claim_count": self.manual_claim_count,
      "claim_text_required_count": self.claim_text_required_count,
      "evidence_link_count": self.evidence_link_count,
      "gap_count": self.gap_count,
      "demo_polish_pack_path": self.demo_polish_pack_path,
      "demo_readiness_status": self.demo_readiness_status,
      "overall_status": self.overall_status,
      "next_user_action": self.next_user_action,
      "step_statuses": [s.to_dict() for s in self.step_statuses],
      "output_dir": self.output_dir,
      "manifest_path": self.manifest_path,
      "no_claim_text_generated": self.no_claim_text_generated,
      "no_cloud_build": self.no_cloud_build,
      "no_cloud_run_deploy": self.no_cloud_run_deploy,
      "no_email_send": self.no_email_send,
      "no_scheduler_start": self.no_scheduler_start,
      "warnings": self.warnings,
    }
