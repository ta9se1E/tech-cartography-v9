"""Approved member live digest email send via SMTP (Phase 25Q)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from tech_cartography.runtime.approved_member_send_config import (
  approved_member_block_message,
  can_send_approved_member_email,
  email_domain,
  get_confirmation_text,
  is_approved_member_recipient,
  is_approved_member_send_enabled,
  normalize_email,
)
from tech_cartography.runtime.cloud_run_config import is_email_send_disabled
from tech_cartography.runtime.email_send_config import mask_recipient, resolve_live_smtp_settings
from tech_cartography.runtime.live_artifact_paths import (
  check_directory_writable,
  get_live_approved_member_send_dir,
)
from tech_cartography.services.live_digest_preview import (
  find_latest_live_digest_preview_path,
  load_live_digest_preview,
)
from tech_cartography.services.live_email_sender import (
  LIVE_EMAIL_SAFETY_NOTICE,
  build_outbound_body,
  _default_smtp_send,
)
from tech_cartography.services.live_run_history import (
  attach_user_run_metadata,
  copy_user_run_metadata,
  generate_run_id,
  map_result_status,
  record_live_run,
)

ACTION_TYPE = "live_approved_member_email_send"
PROVIDER = "smtp"
SEND_MODE = "approved_member_manual"

_SENSITIVE_PATTERN = re.compile(
  r"(smtp_password|api[_-]?key|authorization|token|secret|oauth)",
  re.IGNORECASE,
)


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(iso_ts: str) -> str:
  return iso_ts.replace(":", "").replace("-", "")


def _safety_flags(
  *,
  recipient_is_approved: bool,
  confirmation_matched: bool,
) -> dict[str, bool]:
  return {
    "approved_member_send_enabled": is_approved_member_send_enabled(),
    "disable_email_send": is_email_send_disabled(),
    "recipient_is_approved": recipient_is_approved,
    "confirmation_matched": confirmation_matched,
    "no_cc_bcc": True,
    "manual_only": True,
  }


def _block_result(
  *,
  error: str,
  message: str,
  recipient: str = "",
  preview_source_path: str | None = None,
  confirmation_matched: bool = False,
) -> dict[str, Any]:
  recipient_norm = normalize_email(recipient)
  return {
    "ok": False,
    "status": error,
    "error": error,
    "message": message,
    "recipient_email": recipient_norm or None,
    "recipient_domain": email_domain(recipient_norm) if recipient_norm else None,
    "recipient_masked": mask_recipient(recipient) if recipient else "",
    "sent_at": None,
    "provider": PROVIDER,
    "preview_source_path": preview_source_path,
    "send_mode": SEND_MODE,
    "action_type": ACTION_TYPE,
    "saved_paths": {},
    "safety_flags": _safety_flags(
      recipient_is_approved=is_approved_member_recipient(recipient_norm) if recipient_norm else False,
      confirmation_matched=confirmation_matched,
    ),
  }


def build_approved_member_send_log_payload(
  result: dict[str, Any],
  *,
  subject: str,
  digest_preview_artifact: str | None,
) -> dict[str, Any]:
  payload = {
    "timestamp": result.get("sent_at") or _utc_now_iso(),
    "run_id": result.get("run_id"),
    "action_type": ACTION_TYPE,
    "status": map_result_status(ok=result.get("ok"), error=result.get("error")),
    "user_id": result.get("created_by_user_id"),
    "auth_provider": result.get("created_by_auth_provider"),
    "role": result.get("created_by_role"),
    "recipient_email": result.get("recipient_email"),
    "recipient_domain": result.get("recipient_domain"),
    "digest_preview_artifact": digest_preview_artifact,
    "subject": subject,
    "sent_at": result.get("sent_at"),
    "error_summary": None if result.get("ok") else str(result.get("message") or result.get("error") or ""),
    "safety_flags": result.get("safety_flags") or {},
    "send_mode": SEND_MODE,
    "provider": PROVIDER,
    "safety_notice": LIVE_EMAIL_SAFETY_NOTICE,
  }
  return copy_user_run_metadata(payload, result)


def render_approved_member_send_log_markdown(payload: dict[str, Any]) -> str:
  lines = [
    "# Live Approved Member Email Send Log",
    "",
    f"- timestamp: {payload.get('timestamp')}",
    f"- run_id: {payload.get('run_id')}",
    f"- action_type: {payload.get('action_type')}",
    f"- status: {payload.get('status')}",
    f"- user_id: {payload.get('user_id')}",
    f"- role: {payload.get('role')}",
    f"- auth_provider: {payload.get('auth_provider')}",
    f"- recipient_email: {payload.get('recipient_email')}",
    f"- recipient_domain: {payload.get('recipient_domain')}",
    f"- digest_preview_artifact: {payload.get('digest_preview_artifact')}",
    f"- subject: {payload.get('subject')}",
    f"- sent_at: {payload.get('sent_at')}",
    f"- error_summary: {payload.get('error_summary') or '(none)'}",
    "",
    "## safety_flags",
    "",
  ]
  flags = payload.get("safety_flags") or {}
  for key, value in sorted(flags.items()):
    lines.append(f"- {key}: {value}")
  lines.extend(["", "## safety_notice", "", str(payload.get("safety_notice") or LIVE_EMAIL_SAFETY_NOTICE), ""])
  return "\n".join(lines).strip() + "\n"


def save_live_approved_member_send_log(
  result: dict[str, Any],
  *,
  subject: str,
  digest_preview_artifact: str | None,
  output_root: Path | str,
) -> dict[str, str]:
  out_dir = get_live_approved_member_send_dir(output_root)
  writable, message = check_directory_writable(out_dir)
  if not writable:
    raise ValueError(message or f"Cannot write approved member send log to {out_dir}")

  sent_at = str(result.get("sent_at") or _utc_now_iso())
  slug = _timestamp_slug(sent_at)
  json_path = out_dir / f"live_approved_member_send_{slug}.json"
  md_path = out_dir / f"live_approved_member_send_{slug}.md"

  payload = build_approved_member_send_log_payload(
    result,
    subject=subject,
    digest_preview_artifact=digest_preview_artifact,
  )
  serialized = json.dumps(payload, indent=2, ensure_ascii=False)
  if _SENSITIVE_PATTERN.search(serialized) or "SMTP_PASSWORD" in serialized:
    raise ValueError("Refusing to save log containing sensitive material")

  json_path.write_text(serialized + "\n", encoding="utf-8")
  md_path.write_text(render_approved_member_send_log_markdown(payload), encoding="utf-8")
  return {"json": str(json_path), "markdown": str(md_path)}


def send_live_digest_email_to_approved_member(
  *,
  recipient: str,
  confirm_text: str,
  output_root: Path | str,
  login_required: bool,
  is_authenticated: bool,
  auth_role: str,
  preview: dict[str, Any] | None = None,
  preview_source_path: str | None = None,
  cc: str | None = None,
  bcc: str | None = None,
  smtp_send_fn: Callable[..., None] | None = None,
  user_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
  """Send one digest email to a pre-approved member. Never raises; never returns secrets."""
  run_id = generate_run_id()
  started_at = _utc_now_iso()
  cleaned_recipient = normalize_email(recipient)
  source_path = preview_source_path
  theme_name = str((preview or {}).get("theme_name") or "").strip() or None
  expected_confirm = get_confirmation_text()
  confirmation_matched = str(confirm_text or "") == expected_confirm

  def _finalize(result: dict[str, Any]) -> dict[str, Any]:
    result = dict(result)
    result["run_id"] = run_id
    record_live_run(
      action_type=ACTION_TYPE,
      status=map_result_status(ok=result.get("ok"), error=result.get("error")),
      run_id=run_id,
      started_at=started_at,
      user_context=user_context,
      theme_name=theme_name,
      input_summary=(
        f"recipient={mask_recipient(cleaned_recipient)} "
        f"domain={email_domain(cleaned_recipient) or '(unknown)'}"
      ),
      output_artifact_paths=result.get("saved_paths") or {},
      source_artifact_paths=[source_path] if source_path else [],
      error_summary=None if result.get("ok") else str(result.get("message") or result.get("error") or ""),
      project_root=output_root,
    )
    return result

  if cc or bcc:
    return _finalize(
      _block_result(
        error="cc_bcc_not_allowed",
        message=approved_member_block_message("cc_bcc_not_allowed"),
        recipient=cleaned_recipient,
        preview_source_path=source_path,
        confirmation_matched=confirmation_matched,
      ),
    )
  if login_required and not is_authenticated:
    return _finalize(_block_result(error="login_required", message=approved_member_block_message("login_required")))
  if login_required and str(auth_role or "member") != "admin":
    return _finalize(
      _block_result(error="member_not_allowed", message=approved_member_block_message("member_not_allowed")),
    )
  if not confirmation_matched:
    return _finalize(
      _block_result(
        error="confirm_text_mismatch",
        message=approved_member_block_message("confirm_text_mismatch"),
        recipient=cleaned_recipient,
        preview_source_path=source_path,
        confirmation_matched=False,
      ),
    )

  allowed, block_reason = can_send_approved_member_email(cleaned_recipient)
  if not allowed:
    return _finalize(
      _block_result(
        error=block_reason or "blocked",
        message=approved_member_block_message(block_reason),
        recipient=cleaned_recipient,
        preview_source_path=source_path,
        confirmation_matched=True,
      ),
    )

  if preview is None:
    latest_path = find_latest_live_digest_preview_path(output_root)
    if latest_path is None:
      return _finalize(_block_result(error="missing_preview", message=approved_member_block_message("missing_preview")))
    source_path = str(latest_path)
    preview = load_live_digest_preview(latest_path)
    theme_name = str((preview or {}).get("theme_name") or "").strip() or None
  if not preview:
    return _finalize(
      _block_result(
        error="missing_preview",
        message=approved_member_block_message("missing_preview"),
        recipient=cleaned_recipient,
        preview_source_path=source_path,
        confirmation_matched=True,
      ),
    )

  subject = str(preview.get("subject") or "Live Digest Preview")
  plain_body = str(preview.get("body") or preview.get("plain_text_body") or "")
  outbound_body = build_outbound_body(plain_text_body=plain_body)

  settings = resolve_live_smtp_settings()
  host = str(settings.get("host") or "")
  port = int(settings.get("port") or 0)
  username = str(settings.get("username") or "")
  password = str(settings.get("password") or "")
  sender = str(settings.get("sender") or username)

  sender_fn = smtp_send_fn or _default_smtp_send
  sent_at = _utc_now_iso()
  try:
    sender_fn(
      host=host,
      port=port,
      username=username,
      password=password,
      sender=sender,
      recipient=cleaned_recipient,
      subject=subject,
      body=outbound_body,
    )
  except OSError:
    return _finalize(
      {
        "ok": False,
        "status": "smtp_failed",
        "error": "smtp_failed",
        "message": "SMTP送信に失敗しました。",
        "recipient_email": cleaned_recipient,
        "recipient_domain": email_domain(cleaned_recipient),
        "recipient_masked": mask_recipient(cleaned_recipient),
        "sent_at": None,
        "provider": PROVIDER,
        "preview_source_path": source_path,
        "send_mode": SEND_MODE,
        "action_type": ACTION_TYPE,
        "saved_paths": {},
        "safety_flags": _safety_flags(recipient_is_approved=True, confirmation_matched=True),
      },
    )

  result = {
    "ok": True,
    "status": "sent",
    "message": "承認済みメンバーへ Digest を1通送信しました。",
    "recipient_email": cleaned_recipient,
    "recipient_domain": email_domain(cleaned_recipient),
    "recipient_masked": mask_recipient(cleaned_recipient),
    "sent_at": sent_at,
    "provider": PROVIDER,
    "preview_source_path": source_path,
    "send_mode": SEND_MODE,
    "action_type": ACTION_TYPE,
    "subject": subject,
    "saved_paths": {},
    "safety_flags": _safety_flags(recipient_is_approved=True, confirmation_matched=True),
  }
  result = attach_user_run_metadata(result, user_context=user_context, run_id=run_id)
  try:
    result["saved_paths"] = save_live_approved_member_send_log(
      result,
      subject=subject,
      digest_preview_artifact=source_path,
      output_root=output_root,
    )
  except (OSError, ValueError):
    result["message"] = "送信は成功しましたが、送信ログの保存に失敗しました。"
  return _finalize(result)
