"""Tests for email send log (Phase 24.2)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.delivery.send_log import (
  EmailSendLog,
  load_latest_send_log,
  sanitize_log_message,
  save_send_log,
)


def test_save_and_load_send_log(tmp_path: Path) -> None:
  log = EmailSendLog(
    log_id="sendlog-test",
    created_at="2026-06-20T00:00:00+00:00",
    publication_number="US-1",
    subject="Test",
    to_count=1,
    cc_count=0,
    status="dry_run",
    message="dry-run message",
  )
  paths = save_send_log(log, tmp_path)
  assert paths["send_log_json"].exists()
  assert paths["send_log_latest"].exists()
  assert paths["send_log_index"].exists()

  loaded = load_latest_send_log(tmp_path, "US-1")
  assert loaded is not None
  assert loaded.log_id == "sendlog-test"


def test_sanitize_log_message_masks_password() -> None:
  raw = "SMTP failed password=secret123 TC_SMTP_PASSWORD=abc SMTP_PASSWORD=xyz"
  cleaned = sanitize_log_message(raw)
  assert "secret123" not in cleaned
  assert "TC_SMTP_PASSWORD(非表示)" in cleaned or "***" in cleaned
  assert "SMTP_PASSWORD(非表示)" in cleaned
