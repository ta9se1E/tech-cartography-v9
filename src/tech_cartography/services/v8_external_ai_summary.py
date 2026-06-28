"""External AI summary placeholder service (Phase 27R.5) — design only, no API calls."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tech_cartography.runtime.v8_external_ai_config import (
  EXTERNAL_AI_SAFETY_NOTICES,
  external_ai_execution_allowed,
)

FORBIDDEN_OUTPUT_PATTERNS: tuple[str, ...] = (
  "出願できます",
  "回避できます",
  "侵害リスク",
  "無効理由",
  "証明済み",
  "http://",
  "https://",
  "doi:",
  "DOI:",
)

ALLOWED_SUMMARY_TARGETS: tuple[str, ...] = (
  "top5_ranking_explanation",
  "evidence_map_executive_summary",
  "gap_executive_summary",
  "weekly_digest_draft",
)


@dataclass
class ExternalAiSummaryPlan:
  target: str
  prompt_outline: str
  source_artifacts: list[str] = field(default_factory=list)
  output_label: str = "draft summary"
  human_review_required: bool = True
  execution_status: str = "disabled"
  future_connections: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class ExternalAiSummaryValidation:
  ok: bool
  issues: list[str] = field(default_factory=list)
  requires_human_review: bool = True

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


def build_external_ai_summary_prompt(
  *,
  target: str,
  case_id: str,
  source_artifacts: list[str] | None = None,
) -> ExternalAiSummaryPlan:
  """Build prompt plan from existing artifacts — does not call external APIs."""
  if target not in ALLOWED_SUMMARY_TARGETS:
    target = "top5_ranking_explanation"
  artifacts = list(source_artifacts or [])
  outline = (
    f"Case {case_id}: summarize existing {target} from local artifacts only. "
    "Output: next verification points, draft summary, no generated claims/DOI/URLs."
  )
  return ExternalAiSummaryPlan(
    target=target,
    prompt_outline=outline,
    source_artifacts=artifacts,
    output_label="draft summary — human review required",
    human_review_required=True,
    execution_status="disabled" if not external_ai_execution_allowed() else "ready_but_not_implemented",
    future_connections=[
      "Weekly Digest draft",
      "Watch Profile update proposal",
      "Scope Expansion / Feedback",
      "Email preview",
      "Scheduler follow-up plan",
    ],
  )


def render_external_ai_summary_plan(plan: ExternalAiSummaryPlan) -> str:
  lines = [
    f"# External AI Summary Plan — {plan.target}",
    "",
    f"- execution_status: {plan.execution_status}",
    f"- output_label: {plan.output_label}",
    f"- human_review_required: {plan.human_review_required}",
    "",
    "## Prompt outline",
    plan.prompt_outline,
    "",
    "## Source artifacts",
    *[f"- {a}" for a in plan.source_artifacts],
    "",
    "## Future connections",
    *[f"- {c}" for c in plan.future_connections],
    "",
    "## Safety",
    *[f"- {n}" for n in EXTERNAL_AI_SAFETY_NOTICES],
  ]
  return "\n".join(lines)


def validate_external_ai_summary_output(text: str) -> ExternalAiSummaryValidation:
  """Validate draft external AI output against safety rules."""
  issues: list[str] = []
  for pattern in FORBIDDEN_OUTPUT_PATTERNS:
    if pattern in text:
      issues.append(f"forbidden_pattern: {pattern}")
  if "source trace" not in text.lower() and "artifact" not in text.lower() and "既存" not in text:
    issues.append("missing_source_trace_hint")
  return ExternalAiSummaryValidation(
    ok=len(issues) == 0,
    issues=issues,
    requires_human_review=True,
  )


def execute_external_ai_summary(*args: Any, **kwargs: Any) -> dict[str, Any]:
  """Explicitly disabled — external API calls are not implemented in Phase 27R.5."""
  raise RuntimeError(
    "External AI summary execution is disabled. "
    "Set ENABLE_EXTERNAL_AI_SUMMARY=true only after human approval — not available in submission demo."
  )
