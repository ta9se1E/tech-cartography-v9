"""Email send log persistence for manual test sending (Phase 24.2)."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from tech_cartography.web_signals.schema import utc_now_iso

STATUS_DRY_RUN = "dry_run"
STATUS_DRAFT_SAVED = "draft_saved"
STATUS_SENT = "sent"
STATUS_BLOCKED_MISSING_RECIPIENT = "blocked_missing_recipient"
STATUS_BLOCKED_RECIPIENT_DISABLED = "blocked_recipient_disabled"
STATUS_BLOCKED_MISSING_ADAPTER = "blocked_missing_adapter"
STATUS_FAILED = "failed"

_SECRET_TOKENS = ("password", "passwd", "secret", "api_key", "apikey", "token")


@dataclass
class EmailSendLog:
  log_id: str
  created_at: str
  publication_number: str
  subject: str
  to_count: int
  cc_count: int
  status: str
  message: str
  draft_path: str | None = None
  html_path: str | None = None
  json_path: str | None = None
  error_summary: str | None = None
  recipient_group: str | None = None

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> EmailSendLog:
    return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def sanitize_log_message(message: str) -> str:
  """Remove secret-like tokens from log messages."""
  text = str(message or "")
  for token in _SECRET_TOKENS:
    text = re.sub(rf"({token}\s*[=:]\s*)(\S+)", r"\1***", text, flags=re.IGNORECASE)
  if "TC_SMTP_PASSWORD" in text:
    text = text.replace("TC_SMTP_PASSWORD", "TC_SMTP_PASSWORD(非表示)")
  return text


def save_send_log(log: EmailSendLog, output_dir: Path | str) -> dict[str, Path]:
  log_dir = Path(output_dir) / "email_send_logs"
  log_dir.mkdir(parents=True, exist_ok=True)
  pub = log.publication_number
  timestamp = log.created_at.replace(":", "").replace("+", "p")[:15]

  paths = {
    "send_log_json": log_dir / f"send_log_{timestamp}_{pub}.json",
    "send_log_latest": log_dir / f"send_log_latest_{pub}.json",
    "send_log_index": log_dir / "send_log_index.json",
  }

  payload = log.to_dict()
  payload["message"] = sanitize_log_message(payload.get("message", ""))
  if payload.get("error_summary"):
    payload["error_summary"] = sanitize_log_message(str(payload["error_summary"]))

  encoded = json.dumps(payload, indent=2, ensure_ascii=False)
  paths["send_log_json"].write_text(encoded, encoding="utf-8")
  paths["send_log_latest"].write_text(encoded, encoding="utf-8")

  index = _load_send_log_index(log_dir)
  index.append(payload)
  paths["send_log_index"].write_text(
    json.dumps(index[-50:], indent=2, ensure_ascii=False),
    encoding="utf-8",
  )
  return paths


def _load_send_log_index(log_dir: Path) -> list[dict[str, Any]]:
  index_path = log_dir / "send_log_index.json"
  if not index_path.exists():
    return []
  try:
    data = json.loads(index_path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []
  except (OSError, json.JSONDecodeError):
    return []


def load_latest_send_log(output_dir: Path | str, publication_number: str) -> EmailSendLog | None:
  latest = Path(output_dir) / "email_send_logs" / f"send_log_latest_{publication_number}.json"
  if not latest.exists():
    return None
  try:
    data = json.loads(latest.read_text(encoding="utf-8"))
    return EmailSendLog.from_dict(data)
  except (OSError, json.JSONDecodeError, TypeError):
    return None
