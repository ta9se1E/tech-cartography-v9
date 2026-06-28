"""Demo flow / Weekly Watch / Export readiness schema (Phase 27S.7)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tech_cartography.runtime.v8_sources_schema import utc_now_iso

DEMO_FLOW_SAFETY_NOTICES: tuple[str, ...] = (
  "Evidenceは裏取り候補であり、証明ではありません。",
  "Gapは弱点ではなく未確認事項です。",
  "Judge Modeではメール送信・Scheduler起動はOFF（demo mode / not sent）。",
  "FTO、侵害、有効性判断は行いません。",
)

SUBMISSION_DEMO_PUB = "CN108286090A"

READINESS_STATUS_READY = "ready"
READINESS_STATUS_REMAINING = "remaining_next_action"
READINESS_STATUS_DEMO_OFF = "demo_off"


@dataclass
class SubmissionDemoReadinessItem:
  label: str
  status: str
  detail: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class EvidenceAwareWatchContext:
  case_id: str
  gap_output_dir: str = ""
  claim_example_links_dir: str = ""
  watch_profile_path: str = ""
  digest_summary_path: str = ""
  human_review_checklist_path: str = ""
  gap_next_actions_csv: str = ""
  digest_subject_draft: str = ""
  digest_preview_text: str = ""
  watch_profile_text: str = ""
  top3_action_titles: list[str] = field(default_factory=list)
  watch_proposal_bullets: list[str] = field(default_factory=list)
  email_sent: bool = False
  scheduler_started: bool = False
  demo_mode: bool = True
  warnings: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class DemoExportBundleResult:
  case_id: str
  output_dir: str
  generated_at: str = field(default_factory=utc_now_iso)
  files: list[str] = field(default_factory=list)
  source_paths: list[str] = field(default_factory=list)
  warnings: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)
