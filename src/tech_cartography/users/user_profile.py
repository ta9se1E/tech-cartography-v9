"""User profile model and helpers for local email-based identification."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class UserProfile:
  user_id: str
  email: str
  display_name: str | None = None
  company_name: str | None = None
  created_at: str = ""
  updated_at: str = ""
  weekly_email_enabled: bool = False
  preferred_language: str = "ja"
  default_watch_theme: str | None = None
  last_run_id: str | None = None
  weekly_email_day: str = "monday"
  weekly_email_time: str = "09:00"


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_email(email: str) -> str:
  return str(email or "").strip().lower()


def validate_email(email: str) -> bool:
  normalized = normalize_email(email)
  return bool(normalized and _EMAIL_RE.match(normalized))


def build_user_id(email: str) -> str:
  normalized = normalize_email(email)
  digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
  return digest[:16]


def create_user_profile(
  email: str,
  display_name: str | None = None,
  company_name: str | None = None,
) -> UserProfile:
  normalized = normalize_email(email)
  if not validate_email(normalized):
    raise ValueError(f"Invalid email: {email}")
  now = _utc_now_iso()
  return UserProfile(
    user_id=build_user_id(normalized),
    email=normalized,
    display_name=(display_name or "").strip() or None,
    company_name=(company_name or "").strip() or None,
    created_at=now,
    updated_at=now,
    weekly_email_enabled=False,
    preferred_language="ja",
    default_watch_theme=None,
    last_run_id=None,
  )


def user_profile_to_dict(profile: UserProfile) -> dict:
  return asdict(profile)


def user_profile_from_dict(data: dict) -> UserProfile:
  return UserProfile(
    user_id=str(data.get("user_id", "")),
    email=str(data.get("email", "")),
    display_name=data.get("display_name") or None,
    company_name=data.get("company_name") or None,
    created_at=str(data.get("created_at", "")),
    updated_at=str(data.get("updated_at", "")),
    weekly_email_enabled=bool(data.get("weekly_email_enabled", False)),
    preferred_language=str(data.get("preferred_language", "ja")),
    default_watch_theme=data.get("default_watch_theme") or None,
    last_run_id=data.get("last_run_id") or None,
    weekly_email_day=str(data.get("weekly_email_day", "monday")),
    weekly_email_time=str(data.get("weekly_email_time", "09:00")),
  )
