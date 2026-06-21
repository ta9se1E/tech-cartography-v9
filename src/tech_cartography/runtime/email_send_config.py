"""Email send configuration for live self-only digest test (Phase 25G)."""

from __future__ import annotations

import os
import re
from typing import Any

from tech_cartography.runtime.cloud_run_config import DISABLE_EMAIL_SEND_ENV, is_email_send_disabled

EMAIL_SEND_MODE_ENV = "EMAIL_SEND_MODE"
EMAIL_SENDER_ENV = "EMAIL_SENDER"
EMAIL_RECIPIENT_ALLOWLIST_ENV = "EMAIL_RECIPIENT_ALLOWLIST"
SMTP_HOST_ENV = "SMTP_HOST"
SMTP_PORT_ENV = "SMTP_PORT"
SMTP_USERNAME_ENV = "SMTP_USERNAME"
SMTP_PASSWORD_ENV = "SMTP_PASSWORD"

SELF_ONLY_SEND_MODE = "self_only"
ALLOWED_SMTP_PORTS: frozenset[int] = frozenset({465, 587})

_INVALID_SECRET_VALUES: frozenset[str] = frozenset(
  {"", "dummy", "placeholder", "<secret-manager-only>"},
)


def _env(name: str) -> str:
  return str(os.environ.get(name, "") or "").strip()


def get_email_send_mode() -> str:
  return _env(EMAIL_SEND_MODE_ENV).lower()


def is_self_only_send_mode() -> bool:
  return get_email_send_mode() == SELF_ONLY_SEND_MODE


def parse_recipient_allowlist() -> list[str]:
  raw = _env(EMAIL_RECIPIENT_ALLOWLIST_ENV)
  if not raw:
    return []
  return [part.strip().lower() for part in raw.split(",") if part.strip()]


def is_recipient_allowed(recipient: str) -> bool:
  candidate = str(recipient or "").strip().lower()
  if not candidate:
    return False
  allowlist = parse_recipient_allowlist()
  if not allowlist:
    return False
  return candidate in allowlist


def mask_recipient(recipient: str) -> str:
  email = str(recipient or "").strip()
  if "@" not in email:
    return "***"
  local, domain = email.split("@", 1)
  if len(local) <= 1:
    masked_local = "*"
  else:
    masked_local = f"{local[0]}***"
  return f"{masked_local}@{domain}"


def _is_configured_secret(value: str) -> bool:
  normalized = value.strip()
  if not normalized:
    return False
  return normalized.lower() not in _INVALID_SECRET_VALUES


def resolve_live_smtp_settings() -> dict[str, Any]:
  """Resolve SMTP settings for live send. Password never included in status dicts."""
  host = _env(SMTP_HOST_ENV)
  port_raw = _env(SMTP_PORT_ENV)
  username = _env(SMTP_USERNAME_ENV) or _env("SMTP_USER")
  password = _env(SMTP_PASSWORD_ENV) or _env("TC_SMTP_PASSWORD")
  sender = _env(EMAIL_SENDER_ENV) or username
  port: int | None = None
  if port_raw:
    try:
      port = int(port_raw)
    except ValueError:
      port = None
  return {
    "host": host or None,
    "port": port,
    "username": username or None,
    "password": password if _is_configured_secret(password) else None,
    "sender": sender or None,
  }


def missing_smtp_fields() -> list[str]:
  settings = resolve_live_smtp_settings()
  missing: list[str] = []
  if not settings.get("host"):
    missing.append("SMTP_HOST")
  port = settings.get("port")
  if port is None or port not in ALLOWED_SMTP_PORTS:
    missing.append("SMTP_PORT")
  if not settings.get("username"):
    missing.append("SMTP_USERNAME")
  if not settings.get("password"):
    missing.append("SMTP_PASSWORD")
  if not settings.get("sender"):
    missing.append("EMAIL_SENDER")
  return missing


def get_email_send_status() -> dict[str, Any]:
  """Admin-safe status — no secrets."""
  return {
    "disabled_by_env": is_email_send_disabled(),
    "send_mode": get_email_send_mode() or "(unset)",
    "self_only_mode": is_self_only_send_mode(),
    "allowlist_count": len(parse_recipient_allowlist()),
    "smtp_configured": len(missing_smtp_fields()) == 0,
    "missing_smtp_fields": missing_smtp_fields(),
  }


def can_send_self_only_email(recipient: str) -> tuple[bool, str | None]:
  """Return (allowed, block_reason). Never raises."""
  if is_email_send_disabled():
    return False, "disabled_by_env"
  if not is_self_only_send_mode():
    return False, "invalid_send_mode"
  if not is_recipient_allowed(recipient):
    return False, "recipient_not_allowed"
  missing = missing_smtp_fields()
  if missing:
    return False, "missing_smtp_config"
  return True, None


def self_only_block_message(block_reason: str | None) -> str:
  mapping = {
    "disabled_by_env": "メール送信は無効です（DISABLE_EMAIL_SEND=true）。",
    "invalid_send_mode": "EMAIL_SEND_MODE=self_only の場合のみ送信できます。",
    "recipient_not_allowed": "recipient が EMAIL_RECIPIENT_ALLOWLIST に含まれていません。",
    "missing_smtp_config": "SMTP 設定が不足しています（host/port/username/password）。",
    "confirm_text_mismatch": "確認テキストが一致しません。SEND TO MYSELF と入力してください。",
    "login_required": "ログイン後に実行できます。",
    "admin_required": "管理者のみ実行できます。",
    "missing_preview": "latest live_digest_preview がありません。",
  }
  return mapping.get(str(block_reason or ""), "送信条件を満たしていません。")


__all__ = [
  "ALLOWED_SMTP_PORTS",
  "DISABLE_EMAIL_SEND_ENV",
  "EMAIL_RECIPIENT_ALLOWLIST_ENV",
  "EMAIL_SENDER_ENV",
  "EMAIL_SEND_MODE_ENV",
  "SELF_ONLY_SEND_MODE",
  "SMTP_HOST_ENV",
  "SMTP_PASSWORD_ENV",
  "SMTP_PORT_ENV",
  "SMTP_USERNAME_ENV",
  "can_send_self_only_email",
  "get_email_send_mode",
  "get_email_send_status",
  "is_recipient_allowed",
  "is_self_only_send_mode",
  "mask_recipient",
  "missing_smtp_fields",
  "parse_recipient_allowlist",
  "resolve_live_smtp_settings",
  "self_only_block_message",
]
