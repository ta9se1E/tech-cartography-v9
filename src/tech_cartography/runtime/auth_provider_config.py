"""Auth provider mode configuration (Phase 25N)."""

from __future__ import annotations

import os

AUTH_PROVIDER_MODE_ENV = "AUTH_PROVIDER_MODE"
IAP_JWT_VERIFY_MODE_ENV = "IAP_JWT_VERIFY_MODE"
IAP_EXPECTED_AUDIENCE_ENV = "IAP_EXPECTED_AUDIENCE"

ADMIN_EMAILS_ENV = "TECH_CARTOGRAPHY_ADMIN_EMAILS"
MEMBER_EMAILS_ENV = "TECH_CARTOGRAPHY_MEMBER_EMAILS"
ALLOWED_EMAIL_DOMAINS_ENV = "TECH_CARTOGRAPHY_ALLOWED_EMAIL_DOMAINS"

VALID_AUTH_PROVIDER_MODES = frozenset({"basic", "iap", "hybrid"})
VALID_IAP_JWT_VERIFY_MODES = frozenset({"off", "optional", "strict"})


def get_auth_provider_mode() -> str:
  raw = str(os.environ.get(AUTH_PROVIDER_MODE_ENV, "") or "").strip().lower()
  if raw in VALID_AUTH_PROVIDER_MODES:
    return raw
  return "basic"


def get_iap_jwt_verify_mode() -> str:
  raw = str(os.environ.get(IAP_JWT_VERIFY_MODE_ENV, "") or "").strip().lower()
  if raw in VALID_IAP_JWT_VERIFY_MODES:
    return raw
  return "off"


def get_iap_expected_audience() -> str:
  return str(os.environ.get(IAP_EXPECTED_AUDIENCE_ENV, "") or "").strip()


def parse_csv_env(name: str) -> list[str]:
  raw = str(os.environ.get(name, "") or "").strip()
  if not raw:
    return []
  return [item.strip().lower() for item in raw.split(",") if item.strip()]


def get_admin_emails() -> list[str]:
  return parse_csv_env(ADMIN_EMAILS_ENV)


def get_member_emails() -> list[str]:
  return parse_csv_env(MEMBER_EMAILS_ENV)


def get_allowed_email_domains() -> list[str]:
  return [domain.lstrip("@").lower() for domain in parse_csv_env(ALLOWED_EMAIL_DOMAINS_ENV)]


def auth_provider_mode_summary() -> dict[str, str]:
  return {
    "auth_provider_mode": get_auth_provider_mode(),
    "iap_jwt_verify_mode": get_iap_jwt_verify_mode(),
    "iap_expected_audience_configured": "yes" if get_iap_expected_audience() else "no",
    "admin_emails_configured": "yes" if get_admin_emails() else "no",
    "member_emails_configured": "yes" if get_member_emails() else "no",
    "allowed_email_domains_configured": "yes" if get_allowed_email_domains() else "no",
  }
