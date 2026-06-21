"""Self-only live digest email send via SMTP (Phase 25G)."""

from __future__ import annotations

import json
import re
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Callable

from tech_cartography.runtime.email_send_config import (
  SELF_ONLY_SEND_MODE,
  can_send_self_only_email,
  mask_recipient,
  resolve_live_smtp_settings,
  self_only_block_message,
)
from tech_cartography.runtime.live_artifact_paths import (
  check_directory_writable,
  get_live_email_send_dir,
)
from tech_cartography.services.live_digest_preview import (
  find_latest_live_digest_preview_path,
  load_latest_live_digest_preview,
  load_live_digest_preview,
)

CONFIRMATION_TEXT = "SEND TO MYSELF"
PROVIDER = "smtp"
SEND_MODE = SELF_ONLY_SEND_MODE

LIVE_EMAIL_SAFETY_NOTICE = (
  "This message is a Live Digest Preview test send.\n"
  "Web Signals are review candidates only — not confirmed facts.\n"
  "This is not FTO, infringement, or validity analysis.\n"
  "Primary-source verification is required before any decision."
)

LIVE_EMAIL_SAFETY_NOTICE_JA = (
  "このメールは Live Digest Preview のテスト送信です。\n"
  "Web Signal は確認候補であり、確定事実ではありません。\n"
  "FTO、侵害、有効性判断ではありません。\n"
  "最終判断には原典確認が必要です。"
)

_SENSITIVE_PATTERN = re.compile(
  r"(smtp_password|api[_-]?key|authorization|token|secret)",
  re.IGNORECASE,
)


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(iso_ts: str) -> str:
  return iso_ts.replace(":", "").replace("-", "")


def build_outbound_body(*, plain_text_body: str) -> str:
  body = str(plain_text_body or "").strip()
  footer = "\n\n".join(
    [
      "---",
      LIVE_EMAIL_SAFETY_NOTICE_JA,
      LIVE_EMAIL_SAFETY_NOTICE,
    ],
  )
  if footer.strip() in body:
    return body + "\n"
  return f"{body}\n\n{footer}\n"


def _default_smtp_send(
  *,
  host: str,
  port: int,
  username: str,
  password: str,
  sender: str,
  recipient: str,
  subject: str,
  body: str,
) -> None:
  message = MIMEText(body, "plain", "utf-8")
  message["Subject"] = subject
  message["From"] = sender
  message["To"] = recipient

  if port == 465:
    with smtplib.SMTP_SSL(host, port, timeout=30) as server:
      server.login(username, password)
      server.sendmail(sender, [recipient], message.as_string())
    return

  with smtplib.SMTP(host, port, timeout=30) as server:
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(username, password)
    server.sendmail(sender, [recipient], message.as_string())


def _block_result(*, error: str, message: str, recipient: str = "", preview_source_path: str | None = None) -> dict[str, Any]:
  return {
    "ok": False,
    "status": error,
    "message": message,
    "recipient_masked": mask_recipient(recipient) if recipient else "",
    "sent_at": None,
    "provider": PROVIDER,
    "preview_source_path": preview_source_path,
    "send_mode": SEND_MODE,
    "saved_paths": {},
  }


def send_live_digest_email_self_only(
  *,
  recipient: str,
  confirm_text: str,
  output_root: Path | str,
  login_required: bool,
  is_authenticated: bool,
  auth_role: str,
  preview: dict[str, Any] | None = None,
  preview_source_path: str | None = None,
  smtp_send_fn: Callable[..., None] | None = None,
) -> dict[str, Any]:
  """Send one self-only digest email. Never raises; never returns secrets."""
  cleaned_recipient = str(recipient or "").strip()
  source_path = preview_source_path

  if login_required and not is_authenticated:
    return _block_result(error="login_required", message=self_only_block_message("login_required"))
  if login_required and str(auth_role or "member") != "admin":
    return _block_result(error="admin_required", message=self_only_block_message("admin_required"))
  if str(confirm_text or "") != CONFIRMATION_TEXT:
    return _block_result(
      error="confirm_text_mismatch",
      message=self_only_block_message("confirm_text_mismatch"),
      recipient=cleaned_recipient,
    )

  allowed, block_reason = can_send_self_only_email(cleaned_recipient)
  if not allowed:
    return _block_result(
      error=block_reason or "blocked",
      message=self_only_block_message(block_reason),
      recipient=cleaned_recipient,
      preview_source_path=source_path,
    )

  if preview is None:
    latest_path = find_latest_live_digest_preview_path(output_root)
    if latest_path is None:
      return _block_result(error="missing_preview", message=self_only_block_message("missing_preview"))
    source_path = str(latest_path)
    preview = load_live_digest_preview(latest_path)
  if not preview:
    return _block_result(
      error="missing_preview",
      message=self_only_block_message("missing_preview"),
      recipient=cleaned_recipient,
      preview_source_path=source_path,
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
  except (OSError, smtplib.SMTPException) as exc:
    return {
      "ok": False,
      "status": "smtp_failed",
      "message": f"SMTP送信に失敗しました: {type(exc).__name__}",
      "recipient_masked": mask_recipient(cleaned_recipient),
      "sent_at": None,
      "provider": PROVIDER,
      "preview_source_path": source_path,
      "send_mode": SEND_MODE,
      "saved_paths": {},
    }

  result = {
    "ok": True,
    "status": "sent",
    "message": "自分宛てテスト送信が完了しました（1通）。",
    "recipient_masked": mask_recipient(cleaned_recipient),
    "sent_at": sent_at,
    "provider": PROVIDER,
    "preview_source_path": source_path,
    "send_mode": SEND_MODE,
    "subject": subject,
    "saved_paths": {},
  }
  try:
    result["saved_paths"] = save_live_email_send_log(
      result,
      subject=subject,
      output_root=output_root,
    )
  except (OSError, ValueError):
    result["message"] = "送信は成功しましたが、送信ログの保存に失敗しました。"
  return result


def build_send_log_payload(
  result: dict[str, Any],
  *,
  subject: str,
) -> dict[str, Any]:
  return {
    "sent_at": result.get("sent_at"),
    "recipient_masked": result.get("recipient_masked"),
    "subject": subject,
    "preview_source_path": result.get("preview_source_path"),
    "provider": result.get("provider"),
    "send_mode": result.get("send_mode"),
    "result_status": result.get("status"),
    "safety_notice": LIVE_EMAIL_SAFETY_NOTICE,
  }


def render_send_log_markdown(payload: dict[str, Any]) -> str:
  lines = [
    "# Live Email Send Log",
    "",
    f"- sent_at: {payload.get('sent_at')}",
    f"- recipient_masked: {payload.get('recipient_masked')}",
    f"- subject: {payload.get('subject')}",
    f"- preview_source_path: {payload.get('preview_source_path')}",
    f"- provider: {payload.get('provider')}",
    f"- send_mode: {payload.get('send_mode')}",
    f"- result_status: {payload.get('result_status')}",
    "",
    "## Safety notice",
    "",
    str(payload.get("safety_notice") or LIVE_EMAIL_SAFETY_NOTICE),
    "",
  ]
  return "\n".join(lines).strip() + "\n"


def save_live_email_send_log(
  result: dict[str, Any],
  *,
  subject: str,
  output_root: Path | str,
) -> dict[str, str]:
  out_dir = get_live_email_send_dir(output_root)
  writable, message = check_directory_writable(out_dir)
  if not writable:
    raise ValueError(message or f"Cannot write live email send log to {out_dir}")

  sent_at = str(result.get("sent_at") or _utc_now_iso())
  slug = _timestamp_slug(sent_at)
  json_path = out_dir / f"live_email_send_{slug}.json"
  md_path = out_dir / f"live_email_send_{slug}.md"

  payload = build_send_log_payload(result, subject=subject)
  serialized = json.dumps(payload, indent=2, ensure_ascii=False)
  if _SENSITIVE_PATTERN.search(serialized) or "SMTP_PASSWORD" in serialized:
    raise ValueError("Refusing to save log containing sensitive material")

  json_path.write_text(serialized + "\n", encoding="utf-8")
  md_path.write_text(render_send_log_markdown(payload), encoding="utf-8")
  return {"json": str(json_path), "markdown": str(md_path)}


def load_latest_digest_for_send(output_root: Path | str) -> tuple[dict[str, Any] | None, str | None]:
  latest = find_latest_live_digest_preview_path(output_root)
  if latest is None:
    return None, None
  return load_live_digest_preview(latest), str(latest)
