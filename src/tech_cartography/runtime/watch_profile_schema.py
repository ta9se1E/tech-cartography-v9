"""Watch Profile schema and validation (Phase 25S)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

PROFILE_STATUS_DRAFT = "draft"
PROFILE_STATUS_ACTIVE = "active"
PROFILE_STATUS_ARCHIVED = "archived"

VALID_STATUSES = frozenset({PROFILE_STATUS_DRAFT, PROFILE_STATUS_ACTIVE, PROFILE_STATUS_ARCHIVED})

LIST_FIELDS = (
  "target_materials",
  "target_applications",
  "search_keywords",
  "search_queries",
  "exclude_keywords",
  "target_assignees",
  "competitor_assignees",
  "target_jurisdictions",
  "target_publication_kinds",
  "expansion_candidates",
  "excluded_candidates",
  "source_artifact_paths",
)

FORBIDDEN_PHRASES = (
  "FTO",
  "freedom to operate",
  "infringement",
  "validity analysis",
  "legal opinion",
)

_SENSITIVE_PATTERN = re.compile(
  r"(smtp_password|api[_-]?key|authorization|oauth|jwt|secret)",
  re.IGNORECASE,
)


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def generate_profile_id() -> str:
  return f"wp-{uuid.uuid4().hex[:12]}"


def _parse_list(value: Any) -> list[str]:
  if value is None:
    return []
  if isinstance(value, list):
    return [str(item).strip() for item in value if str(item).strip()]
  if isinstance(value, str):
    return [part.strip() for part in value.replace("\n", ",").split(",") if part.strip()]
  return []


def empty_watch_profile_template(*, theme_name: str = "") -> dict[str, Any]:
  return {
    "profile_id": generate_profile_id(),
    "version": 1,
    "status": PROFILE_STATUS_DRAFT,
    "theme_name": theme_name.strip(),
    "theme_description": "",
    "target_materials": [],
    "target_applications": [],
    "search_keywords": [],
    "search_queries": [],
    "exclude_keywords": [],
    "target_assignees": [],
    "competitor_assignees": [],
    "target_jurisdictions": [],
    "target_publication_kinds": [],
    "source_policy": "human_approved_candidates_only",
    "route_policy": "manual_review_before_execution",
    "deep_dive_policy": "primary_source_verification_required",
    "weekly_priority": "standard",
    "expansion_candidates": [],
    "excluded_candidates": [],
    "human_approval_required": True,
    "created_at": _utc_now_iso(),
    "created_by": "",
    "approved_at": None,
    "approved_by": None,
    "previous_profile_id": None,
    "source_artifact_paths": [],
    "notes": "",
  }


def normalize_watch_profile(raw: dict[str, Any] | None) -> dict[str, Any]:
  base = empty_watch_profile_template()
  if not raw:
    return base
  merged = dict(base)
  merged.update({k: v for k, v in raw.items() if k in base or k in {"profile_id", "version", "status"}})
  for field in LIST_FIELDS:
    merged[field] = _parse_list(raw.get(field))
  merged["theme_name"] = str(raw.get("theme_name") or "").strip()
  merged["theme_description"] = str(raw.get("theme_description") or "").strip()
  merged["notes"] = str(raw.get("notes") or "").strip()
  merged["weekly_priority"] = str(raw.get("weekly_priority") or "standard").strip() or "standard"
  merged["human_approval_required"] = bool(raw.get("human_approval_required", True))
  status = str(raw.get("status") or PROFILE_STATUS_DRAFT).strip().lower()
  merged["status"] = status if status in VALID_STATUSES else PROFILE_STATUS_DRAFT
  merged["profile_id"] = str(raw.get("profile_id") or generate_profile_id()).strip() or generate_profile_id()
  try:
    merged["version"] = int(raw.get("version") or 1)
  except (TypeError, ValueError):
    merged["version"] = 1
  return merged


def _assert_no_forbidden_content(profile: dict[str, Any]) -> list[str]:
  errors: list[str] = []
  serialized = str(profile).lower()
  for phrase in FORBIDDEN_PHRASES:
    if phrase.lower() in serialized:
      errors.append(f"forbidden_phrase:{phrase}")
  if _SENSITIVE_PATTERN.search(serialized):
    errors.append("sensitive_material_detected")
  return errors


def validate_watch_profile_draft(profile: dict[str, Any]) -> tuple[bool, list[str]]:
  normalized = normalize_watch_profile(profile)
  errors: list[str] = []
  if not normalized.get("theme_name"):
    errors.append("theme_name_required")
  if normalized.get("status") != PROFILE_STATUS_DRAFT:
    errors.append("status_must_be_draft")
  if not normalized.get("human_approval_required"):
    errors.append("human_approval_required_must_be_true")
  errors.extend(_assert_no_forbidden_content(normalized))
  return len(errors) == 0, errors


def validate_watch_profile_for_activation(profile: dict[str, Any]) -> tuple[bool, list[str]]:
  normalized = normalize_watch_profile(profile)
  errors: list[str] = []
  if not normalized.get("theme_name"):
    errors.append("theme_name_required")
  if not normalized.get("search_keywords") and not normalized.get("search_queries"):
    errors.append("search_conditions_required")
  if not normalized.get("human_approval_required"):
    errors.append("human_approval_required_must_be_true")
  errors.extend(_assert_no_forbidden_content(normalized))
  return len(errors) == 0, errors


def summarize_watch_profile(profile: dict[str, Any]) -> dict[str, Any]:
  normalized = normalize_watch_profile(profile)
  return {
    "profile_id": normalized.get("profile_id"),
    "version": normalized.get("version"),
    "status": normalized.get("status"),
    "theme_name": normalized.get("theme_name"),
    "search_keyword_count": len(normalized.get("search_keywords") or []),
    "search_query_count": len(normalized.get("search_queries") or []),
    "target_assignee_count": len(normalized.get("target_assignees") or []),
    "weekly_priority": normalized.get("weekly_priority"),
    "human_approval_required": normalized.get("human_approval_required"),
    "created_at": normalized.get("created_at"),
    "approved_at": normalized.get("approved_at"),
  }


def diff_watch_profiles(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
  a = normalize_watch_profile(left)
  b = normalize_watch_profile(right)
  changes: dict[str, Any] = {}
  for field in (
    "theme_name",
    "theme_description",
    "weekly_priority",
    "notes",
    *LIST_FIELDS,
  ):
    if a.get(field) != b.get(field):
      changes[field] = {"before": a.get(field), "after": b.get(field)}
  return {
    "left_profile_id": a.get("profile_id"),
    "right_profile_id": b.get("profile_id"),
    "changed_fields": changes,
    "change_count": len(changes),
  }
