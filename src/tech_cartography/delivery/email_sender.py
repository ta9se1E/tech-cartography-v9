"""Optional SMTP adapter — explicit send only (Phase 24.1)."""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from tech_cartography.delivery.email_outbox import (
  EmailDraft,
  STATUS_BLOCKED_MISSING_ADAPTER,
  STATUS_BLOCKED_MISSING_RECIPIENT,
  STATUS_FAILED,
  STATUS_SENT,
)

SMTP_ENV_KEYS = (
  "TC_SMTP_HOST",
  "TC_SMTP_PORT",
  "TC_SMTP_USER",
  "TC_SMTP_PASSWORD",
  "TC_SMTP_FROM",
)


def can_send_email() -> tuple[bool, str]:
  """Return whether SMTP is configured (no secrets in message)."""
  missing = [key for key in SMTP_ENV_KEYS if not os.environ.get(key, "").strip()]
  if missing:
    return False, f"SMTP not configured. Missing: {', '.join(missing)}"
  return True, "SMTP configuration present."


def send_email_smtp(draft: EmailDraft) -> dict[str, Any]:
  """Send draft via SMTP. Never logs passwords."""
  if not draft.to:
    draft.status = STATUS_BLOCKED_MISSING_RECIPIENT
    return {
      "ok": False,
      "status": draft.status,
      "message": "No recipients configured.",
    }

  ready, reason = can_send_email()
  if not ready:
    draft.status = STATUS_BLOCKED_MISSING_ADAPTER
    return {
      "ok": False,
      "status": draft.status,
      "message": reason,
    }

  host = os.environ["TC_SMTP_HOST"].strip()
  port = int(os.environ["TC_SMTP_PORT"].strip())
  user = os.environ["TC_SMTP_USER"].strip()
  password = os.environ["TC_SMTP_PASSWORD"]
  sender = os.environ["TC_SMTP_FROM"].strip()

  message = MIMEMultipart("alternative")
  message["Subject"] = draft.subject
  message["From"] = sender
  message["To"] = ", ".join(draft.to)
  if draft.cc:
    message["Cc"] = ", ".join(draft.cc)

  message.attach(MIMEText(draft.markdown_body, "plain", "utf-8"))
  message.attach(MIMEText(draft.html_body, "html", "utf-8"))

  recipients = list(draft.to) + list(draft.cc)

  try:
    with smtplib.SMTP(host, port, timeout=30) as server:
      server.starttls()
      server.login(user, password)
      server.sendmail(sender, recipients, message.as_string())
    draft.status = STATUS_SENT
    return {
      "ok": True,
      "status": STATUS_SENT,
      "message": f"Email sent to {len(recipients)} recipient(s).",
      "recipient_count": len(recipients),
    }
  except (OSError, smtplib.SMTPException) as exc:
    draft.status = STATUS_FAILED
    return {
      "ok": False,
      "status": STATUS_FAILED,
      "message": f"SMTP send failed: {type(exc).__name__}",
    }
