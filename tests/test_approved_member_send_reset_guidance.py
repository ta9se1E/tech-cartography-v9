"""Tests for approved member send post-send reset guidance (Phase 25Q.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tech_cartography.runtime.approved_member_send_config import (
  APPROVED_MEMBER_EMAILS_ENV,
  DEFAULT_CONFIRMATION_TEXT,
  ENABLE_APPROVED_MEMBER_SEND_ENV,
)
from tech_cartography.runtime.cloud_run_config import DISABLE_EMAIL_SEND_ENV, DISABLE_SCHEDULER_ENV
from tech_cartography.services.live_approved_member_email_sender import (
  build_approved_member_send_log_payload,
  send_live_digest_email_to_approved_member,
)
from tech_cartography.services.live_run_history import list_run_history_entries


@pytest.fixture
def sample_preview() -> dict:
  return {
    "subject": "[Tech Cartography] Weekly Digest",
    "body": "Digest body.",
    "theme_name": "Carbon Fiber Intelligence",
  }


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  for name in (
    ENABLE_APPROVED_MEMBER_SEND_ENV,
    APPROVED_MEMBER_EMAILS_ENV,
    DISABLE_EMAIL_SEND_ENV,
    DISABLE_SCHEDULER_ENV,
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "EMAIL_SENDER",
  ):
    monkeypatch.delenv(name, raising=False)
  monkeypatch.setenv(ENABLE_APPROVED_MEMBER_SEND_ENV, "true")
  monkeypatch.setenv(APPROVED_MEMBER_EMAILS_ENV, "approved@example.com")
  monkeypatch.setenv(DISABLE_EMAIL_SEND_ENV, "false")
  monkeypatch.setenv(DISABLE_SCHEDULER_ENV, "true")
  monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
  monkeypatch.setenv("SMTP_PORT", "465")
  monkeypatch.setenv("SMTP_USERNAME", "sender@example.com")
  monkeypatch.setenv("SMTP_PASSWORD", "secret-not-real")
  monkeypatch.setenv("EMAIL_SENDER", "sender@example.com")


def test_success_artifact_includes_reset_guidance(sample_preview: dict, tmp_path: Path) -> None:
  result = send_live_digest_email_to_approved_member(
    recipient="approved@example.com",
    confirm_text=DEFAULT_CONFIRMATION_TEXT,
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    preview=sample_preview,
    preview_source_path="preview.json",
    smtp_send_fn=lambda **_: None,
    user_context={
      "user_id": "admin@example.com",
      "role": "admin",
      "auth_provider": "google_iap",
      "is_admin": True,
    },
  )
  assert result["ok"] is True
  assert result.get("reset_required") is True
  assert result.get("post_send_recommended_action") == "disable_email_send"
  assert "SMTP_PASSWORD" not in json.dumps(result)
  text = Path(result["saved_paths"]["json"]).read_text(encoding="utf-8")
  assert "reset_required" in text
  assert "post_send_recommended_action" in text
  assert "secret-not-real" not in text


def test_run_history_includes_operation_metadata(sample_preview: dict, tmp_path: Path) -> None:
  send_live_digest_email_to_approved_member(
    recipient="approved@example.com",
    confirm_text=DEFAULT_CONFIRMATION_TEXT,
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    preview=sample_preview,
    preview_source_path="preview.json",
    smtp_send_fn=lambda **_: None,
    user_context={
      "user_id": "admin@example.com",
      "role": "admin",
      "auth_provider": "google_iap",
      "is_admin": True,
    },
  )
  entries = list_run_history_entries(
    tmp_path,
    action_type="live_approved_member_email_send",
    viewer_user_context={"user_id": "admin@example.com", "role": "admin", "is_admin": True},
  )
  assert entries
  meta = entries[0].get("operation_metadata") or {}
  assert meta.get("post_send_recommended_action") == "disable_email_send"
  assert meta.get("reset_required") is True
  assert meta.get("recipient_masked")
  assert meta.get("recipient_domain") == "example.com"


def test_failed_send_has_no_reset_guidance() -> None:
  payload = build_approved_member_send_log_payload(
    {"ok": False, "error": "blocked", "message": "blocked"},
    subject="Subject",
    digest_preview_artifact="preview.json",
  )
  assert "reset_required" not in payload
