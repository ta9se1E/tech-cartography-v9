"""Email operation safety status — env aggregation without secrets (Phase 25Q.2)."""

from __future__ import annotations

import os
from typing import Any

from tech_cartography.runtime.approved_member_send_config import (
  ENABLE_APPROVED_MEMBER_SEND_ENV,
  is_approved_member_send_enabled,
  parse_approved_member_emails,
)
from tech_cartography.runtime.auth_provider_config import get_admin_emails, get_auth_provider_mode
from tech_cartography.runtime.cloud_run_config import (
  DISABLE_EMAIL_SEND_ENV,
  DISABLE_SCHEDULER_ENV,
  is_email_send_disabled,
  is_scheduler_disabled,
)
from tech_cartography.runtime.email_send_config import (
  EMAIL_SEND_MODE_ENV,
  SMTP_HOST_ENV,
  SMTP_PASSWORD_ENV,
  SMTP_PORT_ENV,
  SMTP_USERNAME_ENV,
  EMAIL_RECIPIENT_ALLOWLIST_ENV,
  EMAIL_SENDER_ENV,
  get_email_send_mode,
  missing_smtp_fields,
  parse_recipient_allowlist,
)

SAFETY_LEVEL_SAFE_OFF = "safe_off"
SAFETY_LEVEL_CONTROLLED = "controlled_manual_send_enabled"
SAFETY_LEVEL_RISKY = "risky_email_enabled"
SAFETY_LEVEL_MISCONFIGURED = "misconfigured"

DEFAULT_RESET_PROJECT_ID = "devops-ai-agent-hackathon-2026"
DEFAULT_RESET_REGION = "us-central1"
DEFAULT_RESET_SERVICE = "tech-cartography-v7-live"

POST_SEND_SAFETY_NOTE = (
  "送信テスト後は ENABLE_APPROVED_MEMBER_SEND=false, DISABLE_EMAIL_SEND=true に戻してください。"
)
POST_SEND_RECOMMENDED_ACTION = "disable_email_send"


def _env(name: str) -> str:
  return str(os.environ.get(name, "") or "").strip()


def _is_smtp_password_configured() -> bool:
  raw = _env(SMTP_PASSWORD_ENV) or _env("TC_SMTP_PASSWORD")
  if not raw:
    return False
  return raw.lower() not in {"", "dummy", "placeholder", "<secret-manager-only>"}


def build_post_send_reset_command(
  *,
  project_id: str = DEFAULT_RESET_PROJECT_ID,
  region: str = DEFAULT_RESET_REGION,
  service: str = DEFAULT_RESET_SERVICE,
) -> str:
  """Return copy-paste gcloud command — no secrets."""
  return (
    f'PROJECT_ID={project_id}\n'
    f'REGION={region}\n'
    f'SERVICE={service}\n\n'
    f'gcloud run services update "$SERVICE" \\\n'
    f'  --region "$REGION" \\\n'
    f'  --project "$PROJECT_ID" \\\n'
    f'  --update-env-vars "ENABLE_APPROVED_MEMBER_SEND=false,DISABLE_EMAIL_SEND=true" \\\n'
    f'  --remove-env-vars TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS,EMAIL_RECIPIENT_ALLOWLIST'
  )


def build_post_send_reset_guidance(*, at_send: bool = False) -> dict[str, Any]:
  """Post-send safety fields for artifacts and run history — no secrets."""
  guidance = {
    "post_send_recommended_action": POST_SEND_RECOMMENDED_ACTION,
    "post_send_safety_note": POST_SEND_SAFETY_NOTE,
    "reset_required": True,
    "reset_command_hint": build_post_send_reset_command(),
  }
  if at_send:
    guidance.update(
      {
        "scheduler_state_at_send": "disabled" if is_scheduler_disabled() else "enabled",
        "disable_email_send_at_send": is_email_send_disabled(),
        "approved_member_send_enabled_at_send": is_approved_member_send_enabled(),
      },
    )
  return guidance


def _compute_safety_level(
  *,
  email_send_disabled: bool,
  approved_member_send_enabled: bool,
  approved_member_count: int,
  smtp_configured: bool,
  scheduler_disabled: bool,
) -> tuple[str, list[str], str]:
  warnings: list[str] = []
  auth_mode = get_auth_provider_mode()
  if auth_mode != "iap":
    warnings.append(f"AUTH_PROVIDER_MODE={auth_mode} — 本番 live では iap を推奨します。")

  if email_send_disabled and not approved_member_send_enabled:
    return (
      SAFETY_LEVEL_SAFE_OFF,
      warnings,
      "メール送信は停止中です。安全状態です。",
    )

  if not email_send_disabled and not smtp_configured:
    return (
      SAFETY_LEVEL_MISCONFIGURED,
      warnings,
      "SMTP設定または承認済み宛先が不足しています。",
    )

  if not email_send_disabled and not scheduler_disabled:
    return (
      SAFETY_LEVEL_RISKY,
      warnings,
      "メール送信が有効で、Schedulerまたは送信範囲に注意が必要です。",
    )

  if (
    not email_send_disabled
    and approved_member_send_enabled
    and approved_member_count > 0
    and scheduler_disabled
    and smtp_configured
  ):
    return (
      SAFETY_LEVEL_CONTROLLED,
      warnings,
      "承認済みメンバーへの手動送信が一時的に有効です。テスト後はOFFに戻してください。",
    )

  if not email_send_disabled and approved_member_send_enabled and approved_member_count == 0:
    return (
      SAFETY_LEVEL_MISCONFIGURED,
      warnings,
      "SMTP設定または承認済み宛先が不足しています。",
    )

  if not email_send_disabled:
    return (
      SAFETY_LEVEL_RISKY,
      warnings,
      "メール送信が有効で、Schedulerまたは送信範囲に注意が必要です。",
    )

  return (
    SAFETY_LEVEL_SAFE_OFF,
    warnings,
    "メール送信は停止中です。安全状態です。",
  )


def get_email_operation_status() -> dict[str, Any]:
  """Admin-safe email operation summary — never returns secret values."""
  email_send_disabled = is_email_send_disabled()
  approved_member_send_enabled = is_approved_member_send_enabled()
  approved_member_count = len(parse_approved_member_emails())
  recipient_allowlist_count = len(parse_recipient_allowlist())
  smtp_configured = len(missing_smtp_fields()) == 0
  scheduler_disabled = is_scheduler_disabled()
  auth_provider_mode = get_auth_provider_mode()
  admin_email_count = len(get_admin_emails())

  safety_level, warnings, status_message = _compute_safety_level(
    email_send_disabled=email_send_disabled,
    approved_member_send_enabled=approved_member_send_enabled,
    approved_member_count=approved_member_count,
    smtp_configured=smtp_configured,
    scheduler_disabled=scheduler_disabled,
  )

  next_action = status_message
  if safety_level in {SAFETY_LEVEL_CONTROLLED, SAFETY_LEVEL_RISKY}:
    next_action = (
      f"{status_message} テスト後は gcloud で "
      "ENABLE_APPROVED_MEMBER_SEND=false, DISABLE_EMAIL_SEND=true に戻してください。"
    )
  elif safety_level == SAFETY_LEVEL_MISCONFIGURED:
    next_action = "SMTP 設定と承認済みメンバー一覧を確認してから送信してください。"

  return {
    "email_send_disabled": email_send_disabled,
    "approved_member_send_enabled": approved_member_send_enabled,
    "approved_member_count": approved_member_count,
    "recipient_allowlist_count": recipient_allowlist_count,
    "email_send_mode": get_email_send_mode() or "(unset)",
    "smtp_configured": smtp_configured,
    "smtp_password_configured": _is_smtp_password_configured(),
    "scheduler_disabled": scheduler_disabled,
    "auth_provider_mode": auth_provider_mode,
    "admin_email_count": admin_email_count,
    "safety_level": safety_level,
    "status_message": status_message,
    "warnings": warnings,
    "next_recommended_action": next_action,
    "reset_command_hint": build_post_send_reset_command(),
    "env_flags": {
      "DISABLE_EMAIL_SEND": email_send_disabled,
      "ENABLE_APPROVED_MEMBER_SEND": approved_member_send_enabled,
      "DISABLE_SCHEDULER": scheduler_disabled,
      "SMTP_HOST_set": bool(_env(SMTP_HOST_ENV)),
      "SMTP_PORT_set": bool(_env(SMTP_PORT_ENV)),
      "SMTP_USERNAME_set": bool(_env(SMTP_USERNAME_ENV)),
      "EMAIL_SENDER_set": bool(_env(EMAIL_SENDER_ENV)),
    },
  }


def safety_level_label_ja(level: str) -> str:
  mapping = {
    SAFETY_LEVEL_SAFE_OFF: "安全（送信OFF）",
    SAFETY_LEVEL_CONTROLLED: "制御付き手動送信ON",
    SAFETY_LEVEL_RISKY: "要注意（送信リスクあり）",
    SAFETY_LEVEL_MISCONFIGURED: "設定不足",
  }
  return mapping.get(level, level)
