"""Evidence Gap schema — structured unknowns for Strategic Watch (Phase 25V)."""

from __future__ import annotations

import re
import uuid
from typing import Any

SOURCE_TYPES: frozenset[str] = frozenset(
  {"patent", "paper", "web_signal", "watch_profile", "digest_preview"},
)

SUPPORT_LEVELS: frozenset[str] = frozenset(
  {
    "no_direct_evidence",
    "single_candidate_source",
    "multiple_candidate_sources",
    "source_supported_but_unverified",
    "human_verified",
  },
)

RECOMMENDED_OWNERS: frozenset[str] = frozenset(
  {"researcher", "patent_reader", "business_development", "human_reviewer"},
)

URGENCY_LEVELS: frozenset[str] = frozenset({"low", "medium", "high"})

CONFIDENCE_LABELS: frozenset[str] = frozenset(
  {"candidate", "weak_signal", "needs_review", "verified_by_human"},
)

CAUTION_FLAG_KEYS: frozenset[str] = frozenset(
  {
    "candidate_information_only",
    "no_legal_judgement",
    "no_fto_judgement",
    "no_infringement_judgement",
    "no_validity_judgement",
  },
)

_SENSITIVE_PATTERN = re.compile(
  r"(smtp_password|tavily_api_key|api[_-]?key\s*[:=]|authorization|oauth|jwt|secret)",
  re.IGNORECASE,
)

DEFAULT_CAUTION_FLAGS: dict[str, bool] = {
  "candidate_information_only": True,
  "no_legal_judgement": True,
  "no_fto_judgement": True,
  "no_infringement_judgement": True,
  "no_validity_judgement": True,
}


def default_safety_flags() -> dict[str, bool]:
  return {
    "no_external_api_call": True,
    "no_email_send": True,
    "no_scheduler_start": True,
    "candidate_information_only": True,
    "legal_judgement": False,
    "fto_judgement": False,
    "infringement_judgement": False,
    "validity_judgement": False,
  }


def new_gap_id() -> str:
  return f"gap-{uuid.uuid4().hex[:10]}"


def _assert_no_sensitive(value: Any) -> None:
  text = str(value)
  if _SENSITIVE_PATTERN.search(text):
    raise ValueError("Evidence gap payload contains sensitive material")


def validate_evidence_gap(gap: dict[str, Any]) -> list[str]:
  """Return validation errors. Empty list means valid."""
  errors: list[str] = []
  required = (
    "gap_id",
    "theme_name",
    "observation",
    "source_types",
    "support_level",
    "what_is_known",
    "what_is_unknown",
    "missing_evidence",
    "why_it_matters",
    "next_verification_action",
    "recommended_owner",
    "urgency",
    "confidence_label",
    "source_artifact_paths",
    "caution_flags",
  )
  for key in required:
    if key not in gap:
      errors.append(f"missing field: {key}")

  support = str(gap.get("support_level") or "")
  if support not in SUPPORT_LEVELS:
    errors.append(f"invalid support_level: {support}")
  if support == "human_verified":
    errors.append("human_verified requires explicit human confirmation input")

  for source in gap.get("source_types") or []:
    if str(source) not in SOURCE_TYPES:
      errors.append(f"invalid source_type: {source}")

  owner = str(gap.get("recommended_owner") or "")
  if owner not in RECOMMENDED_OWNERS:
    errors.append(f"invalid recommended_owner: {owner}")

  urgency = str(gap.get("urgency") or "")
  if urgency not in URGENCY_LEVELS:
    errors.append(f"invalid urgency: {urgency}")

  confidence = str(gap.get("confidence_label") or "")
  if confidence not in CONFIDENCE_LABELS:
    errors.append(f"invalid confidence_label: {confidence}")
  if confidence == "verified_by_human":
    errors.append("verified_by_human must not be assigned automatically")

  flags = gap.get("caution_flags") or {}
  for key in CAUTION_FLAG_KEYS:
    if key not in flags:
      errors.append(f"missing caution_flag: {key}")
    elif flags.get(key) is not True:
      errors.append(f"caution_flag must be true: {key}")

  try:
    _assert_no_sensitive(gap)
  except ValueError as exc:
    errors.append(str(exc))

  return errors


def build_evidence_gap(
  *,
  theme_name: str,
  observation: str,
  source_types: list[str],
  support_level: str,
  what_is_known: str,
  what_is_unknown: str,
  missing_evidence: str,
  why_it_matters: str,
  next_verification_action: str,
  recommended_owner: str,
  urgency: str,
  confidence_label: str,
  source_artifact_paths: list[str] | None = None,
  gap_id: str | None = None,
) -> dict[str, Any]:
  """Build a validated evidence gap dict. Never assigns human_verified / verified_by_human."""
  if support_level == "human_verified":
    raise ValueError("support_level=human_verified is not allowed without human input")
  if confidence_label == "verified_by_human":
    raise ValueError("confidence_label=verified_by_human must not be assigned automatically")

  gap = {
    "gap_id": gap_id or new_gap_id(),
    "theme_name": theme_name.strip(),
    "observation": observation.strip(),
    "source_types": list(source_types),
    "support_level": support_level,
    "what_is_known": what_is_known.strip(),
    "what_is_unknown": what_is_unknown.strip(),
    "missing_evidence": missing_evidence.strip(),
    "why_it_matters": why_it_matters.strip(),
    "next_verification_action": next_verification_action.strip(),
    "recommended_owner": recommended_owner,
    "urgency": urgency,
    "confidence_label": confidence_label,
    "source_artifact_paths": [p for p in (source_artifact_paths or []) if p],
    "caution_flags": dict(DEFAULT_CAUTION_FLAGS),
  }
  errors = validate_evidence_gap(gap)
  if errors:
    raise ValueError("; ".join(errors))
  return gap
