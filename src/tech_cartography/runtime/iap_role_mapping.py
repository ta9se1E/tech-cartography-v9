"""IAP email to role mapping (Phase 25N)."""

from __future__ import annotations

from typing import Any

from tech_cartography.runtime.auth_provider_config import (
  get_admin_emails,
  get_allowed_email_domains,
  get_member_emails,
)


def normalize_email(email: str) -> str:
  return str(email or "").strip().lower()


def email_domain(email: str) -> str | None:
  normalized = normalize_email(email)
  if "@" not in normalized:
    return None
  return normalized.split("@", 1)[1]


def map_email_to_role(email: str) -> dict[str, Any]:
  """Return role mapping result without secrets."""
  normalized = normalize_email(email)
  if not normalized or "@" not in normalized:
    return {
      "status": "invalid",
      "role": None,
      "is_admin": False,
      "message": "email format is invalid",
    }

  if normalized in get_admin_emails():
    return {
      "status": "ok",
      "role": "admin",
      "is_admin": True,
      "message": "matched admin email list",
    }

  if normalized in get_member_emails():
    return {
      "status": "ok",
      "role": "member",
      "is_admin": False,
      "message": "matched member email list",
    }

  domain = email_domain(normalized)
  allowed_domains = get_allowed_email_domains()
  if domain and domain in allowed_domains:
    return {
      "status": "ok",
      "role": "member",
      "is_admin": False,
      "message": f"matched allowed domain: {domain}",
    }

  return {
    "status": "access_denied",
    "role": None,
    "is_admin": False,
    "message": "email is not in admin/member lists or allowed domains",
  }


def role_mapping_status() -> dict[str, Any]:
  return {
    "admin_email_count": len(get_admin_emails()),
    "member_email_count": len(get_member_emails()),
    "allowed_domain_count": len(get_allowed_email_domains()),
    "configured": bool(get_admin_emails() or get_member_emails() or get_allowed_email_domains()),
  }
