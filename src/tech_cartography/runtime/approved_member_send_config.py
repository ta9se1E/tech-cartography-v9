"""Approved member digest send configuration (Phase 25Q)."""

from __future__ import annotations

import os
import re
from typing import Any

from tech_cartography.runtime.cloud_run_config import is_email_send_disabled
from tech_cartography.runtime.email_send_config import missing_smtp_fields

ENABLE_APPROVED_MEMBER_SEND_ENV = "ENABLE_APPROVED_MEMBER_SEND"
APPROVED_MEMBER_EMAILS_ENV = "TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS"
APPROVED_MEMBER_SEND_CONFIRMATION_ENV = "APPROVED_MEMBER_SEND_CONFIRMATION"

DEFAULT_CONFIRMATION_TEXT = "SEND TO APPROVED MEMBER"

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _env(name: str) -> str:
  return str(os.environ.get(name, "") or "").strip()


def _truthy(raw: str) -> bool:
  return raw.strip().lower() in {"1", "true", "yes", "on"}


def is_approved_member_send_enabled() -> bool:
  return _truthy(_env(ENABLE_APPROVED_MEMBER_SEND_ENV))


def get_confirmation_text() -> str:
  configured = _env(APPROVED_MEMBER_SEND_CONFIRMATION_ENV)
  return configured or DEFAULT_CONFIRMATION_TEXT


def normalize_email(email: str) -> str:
  return str(email or "").strip().lower()


def is_valid_email(email: str) -> bool:
  candidate = normalize_email(email)
  return bool(candidate and _EMAIL_PATTERN.match(candidate))


def parse_approved_member_emails() -> list[str]:
  raw = _env(APPROVED_MEMBER_EMAILS_ENV)
  if not raw:
    return []
  seen: set[str] = set()
  emails: list[str] = []
  for part in raw.split(","):
    candidate = normalize_email(part)
    if not candidate or not is_valid_email(candidate):
      continue
    if candidate in seen:
      continue
    seen.add(candidate)
    emails.append(candidate)
  return emails


def email_domain(email: str) -> str | None:
  normalized = normalize_email(email)
  if "@" not in normalized:
    return None
  return normalized.split("@", 1)[1]


def is_approved_member_recipient(recipient: str) -> bool:
  candidate = normalize_email(recipient)
  if not candidate:
    return False
  return candidate in parse_approved_member_emails()


def get_approved_member_send_status() -> dict[str, Any]:
  """Admin-safe status — no secrets."""
  return {
    "feature_enabled": is_approved_member_send_enabled(),
    "email_send_disabled": is_email_send_disabled(),
    "approved_member_count": len(parse_approved_member_emails()),
    "confirmation_text_configured": bool(_env(APPROVED_MEMBER_SEND_CONFIRMATION_ENV)),
    "smtp_configured": len(missing_smtp_fields()) == 0,
    "missing_smtp_fields": missing_smtp_fields(),
  }


def can_send_approved_member_email(recipient: str) -> tuple[bool, str | None]:
  """Return (allowed, block_reason). Never raises."""
  if not is_approved_member_send_enabled():
    return False, "approved_member_send_disabled"
  if is_email_send_disabled():
    return False, "disabled_by_env"
  if not parse_approved_member_emails():
    return False, "approved_list_empty"
  if not is_valid_email(recipient):
    return False, "invalid_recipient"
  if not is_approved_member_recipient(recipient):
    return False, "recipient_not_approved"
  missing = missing_smtp_fields()
  if missing:
    return False, "missing_smtp_config"
  return True, None


def approved_member_block_message(block_reason: str | None) -> str:
  mapping = {
    "approved_member_send_disabled": "承認済みメンバー送信は無効です（ENABLE_APPROVED_MEMBER_SEND=false）。",
    "disabled_by_env": "メール送信は停止中です（DISABLE_EMAIL_SEND=true）。",
    "approved_list_empty": "承認済みメンバー一覧が未設定です。",
    "invalid_recipient": "送信先メールアドレスの形式が不正です。",
    "recipient_not_approved": "送信先は承認済みメンバー一覧に含まれている必要があります。",
    "missing_smtp_config": "SMTP 設定が不足しています。",
    "confirm_text_mismatch": "確認文が一致していません。SEND TO APPROVED MEMBER と入力してください。",
    "login_required": "ログイン後に実行できます。",
    "admin_required": "admin権限が必要です。",
    "member_not_allowed": "admin権限が必要です。",
    "missing_preview": "latest live_digest_preview がありません。",
    "cc_bcc_not_allowed": "CC/BCC は使用できません。",
  }
  return mapping.get(str(block_reason or ""), "送信条件を満たしていません。")
