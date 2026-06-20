"""Optional SMTP adapter — explicit send only (Phase 24.1 / 24.2)."""

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

SMTP_FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
  "host": ("TC_SMTP_HOST", "SMTP_HOST"),
  "port": ("TC_SMTP_PORT", "SMTP_PORT"),
  "user": ("TC_SMTP_USER", "SMTP_USER"),
  "password": ("TC_SMTP_PASSWORD", "SMTP_PASSWORD"),
  "from_email": ("TC_SMTP_FROM", "SMTP_FROM", "SMTP_FROM_EMAIL"),
}

SMTP_FIELD_LABELS: dict[str, tuple[str, str]] = {
  "host": ("host", "SMTP_HOST または TC_SMTP_HOST"),
  "port": ("port", "SMTP_PORT または TC_SMTP_PORT"),
  "user": ("user", "SMTP_USER または TC_SMTP_USER"),
  "password": ("password", "SMTP_PASSWORD(非表示) または TC_SMTP_PASSWORD(非表示)"),
  "from_email": ("from_email", "SMTP_FROM_EMAIL / SMTP_FROM / TC_SMTP_FROM または SMTP_USER"),
}


def _env_value(name: str) -> str:
  return str(os.environ.get(name, "") or "").strip()


def _resolve_field(candidates: tuple[str, ...]) -> tuple[str | None, str | None]:
  for name in candidates:
    value = _env_value(name)
    if value:
      return value, name
  return None, None


def resolve_smtp_settings() -> dict[str, Any]:
  """Resolve SMTP settings from TC_SMTP_* with SMTP_* fallback."""
  values: dict[str, str | None] = {
    "host": None,
    "port": None,
    "user": None,
    "password": None,
    "from_email": None,
  }
  source: dict[str, str | None] = {
    "host": None,
    "port": None,
    "user": None,
    "password": None,
    "from_email": None,
  }

  for field, candidates in SMTP_FIELD_CANDIDATES.items():
    value, env_name = _resolve_field(candidates)
    values[field] = value
    source[field] = env_name

  if not values["from_email"] and values["user"]:
    values["from_email"] = values["user"]
    source["from_email"] = source["user"] or "SMTP_USER"

  return {
    "host": values["host"],
    "port": values["port"],
    "user": values["user"],
    "password": values["password"],
    "from_email": values["from_email"],
    "source": source,
  }


def format_smtp_missing_message(missing_fields: list[str]) -> str:
  labels = [SMTP_FIELD_LABELS[field][0] for field in missing_fields if field in SMTP_FIELD_LABELS]
  env_hints = ", ".join(
    SMTP_FIELD_LABELS[field][1] for field in missing_fields if field in SMTP_FIELD_LABELS
  )
  label_text = ", ".join(labels) if labels else ", ".join(missing_fields)
  return (
    f"SMTP設定が不足しています: {label_text}。"
    f"利用可能な環境変数名: {env_hints}。"
  )


def can_send_email() -> tuple[bool, str]:
  """Return whether SMTP is configured (no secrets in message)."""
  settings = resolve_smtp_settings()
  missing = [field for field in SMTP_FIELD_CANDIDATES if not settings.get(field)]
  if missing:
    return False, format_smtp_missing_message(missing)
  return True, "SMTP設定が利用可能です。"


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

  settings = resolve_smtp_settings()
  host = str(settings["host"]).strip()
  port = int(str(settings["port"]).strip())
  user = str(settings["user"]).strip()
  password = str(settings["password"])
  sender = str(settings["from_email"]).strip()

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
