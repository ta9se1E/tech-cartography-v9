"""Tests for live approved member email sender (Phase 25Q)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tech_cartography.runtime.approved_member_send_config import (
  APPROVED_MEMBER_EMAILS_ENV,
  DEFAULT_CONFIRMATION_TEXT,
  ENABLE_APPROVED_MEMBER_SEND_ENV,
)
from tech_cartography.runtime.cloud_run_config import DISABLE_EMAIL_SEND_ENV
from tech_cartography.services.live_approved_member_email_sender import (
  ACTION_TYPE,
  save_live_approved_member_send_log,
  send_live_digest_email_to_approved_member,
)
from tech_cartography.services.live_run_history import list_run_history_entries


@pytest.fixture
def sample_preview() -> dict:
  return {
    "subject": "[Tech Cartography] Weekly Digest",
    "body": "Digest body with key signals.",
    "plain_text_body": "Digest body with key signals.",
    "safety_notice": "candidate only",
    "created_at": "2026-06-18T12:00:00+00:00",
  }


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  for name in (
    ENABLE_APPROVED_MEMBER_SEND_ENV,
    APPROVED_MEMBER_EMAILS_ENV,
    DISABLE_EMAIL_SEND_ENV,
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "EMAIL_SENDER",
  ):
    monkeypatch.delenv(name, raising=False)


def _configure_send(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(ENABLE_APPROVED_MEMBER_SEND_ENV, "true")
  monkeypatch.setenv(APPROVED_MEMBER_EMAILS_ENV, "approved@example.com")
  monkeypatch.setenv(DISABLE_EMAIL_SEND_ENV, "false")
  monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
  monkeypatch.setenv("SMTP_PORT", "465")
  monkeypatch.setenv("SMTP_USERNAME", "sender@example.com")
  monkeypatch.setenv("SMTP_PASSWORD", "secret-not-real")
  monkeypatch.setenv("EMAIL_SENDER", "sender@example.com")


def test_send_blocked_when_feature_disabled(monkeypatch: pytest.MonkeyPatch, sample_preview: dict, tmp_path: Path) -> None:
  result = send_live_digest_email_to_approved_member(
    recipient="approved@example.com",
    confirm_text=DEFAULT_CONFIRMATION_TEXT,
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    preview=sample_preview,
    preview_source_path="preview.json",
  )
  assert result["ok"] is False
  assert result["error"] == "approved_member_send_disabled"


def test_send_blocked_on_confirm_mismatch(monkeypatch: pytest.MonkeyPatch, sample_preview: dict, tmp_path: Path) -> None:
  _configure_send(monkeypatch)
  result = send_live_digest_email_to_approved_member(
    recipient="approved@example.com",
    confirm_text="WRONG",
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    preview=sample_preview,
    preview_source_path="preview.json",
  )
  assert result["ok"] is False
  assert result["error"] == "confirm_text_mismatch"


def test_send_blocked_for_unapproved_recipient(
  monkeypatch: pytest.MonkeyPatch,
  sample_preview: dict,
  tmp_path: Path,
) -> None:
  _configure_send(monkeypatch)
  result = send_live_digest_email_to_approved_member(
    recipient="other@example.com",
    confirm_text=DEFAULT_CONFIRMATION_TEXT,
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    preview=sample_preview,
    preview_source_path="preview.json",
  )
  assert result["ok"] is False
  assert result["error"] == "recipient_not_approved"


def test_send_blocked_for_member_role(monkeypatch: pytest.MonkeyPatch, sample_preview: dict, tmp_path: Path) -> None:
  _configure_send(monkeypatch)
  result = send_live_digest_email_to_approved_member(
    recipient="approved@example.com",
    confirm_text=DEFAULT_CONFIRMATION_TEXT,
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="member",
    preview=sample_preview,
    preview_source_path="preview.json",
  )
  assert result["ok"] is False
  assert result["error"] == "member_not_allowed"


def test_send_allows_iap_admin_via_user_context_without_session_flag(
  monkeypatch: pytest.MonkeyPatch,
  sample_preview: dict,
  tmp_path: Path,
) -> None:
  _configure_send(monkeypatch)
  calls: list[dict] = []

  def _mock_send(**kwargs: object) -> None:
    calls.append(dict(kwargs))

  user_context = {
    "user_id": "admin@example.com",
    "display_name": "Admin",
    "role": "admin",
    "auth_provider": "google_iap",
    "is_admin": True,
  }
  result = send_live_digest_email_to_approved_member(
    recipient="approved@example.com",
    confirm_text=DEFAULT_CONFIRMATION_TEXT,
    output_root=tmp_path,
    login_required=True,
    is_authenticated=False,
    auth_role="member",
    preview=sample_preview,
    preview_source_path="preview.json",
    smtp_send_fn=_mock_send,
    user_context=user_context,
  )
  assert result["ok"] is True
  assert result["action_type"] == ACTION_TYPE
  assert result.get("error") not in {"login_required", "member_not_allowed"}
  assert "live_approved_member_send" in str(result["saved_paths"].get("json", ""))
  assert len(calls) == 1


def test_send_blocked_for_cc_bcc(monkeypatch: pytest.MonkeyPatch, sample_preview: dict, tmp_path: Path) -> None:
  _configure_send(monkeypatch)
  result = send_live_digest_email_to_approved_member(
    recipient="approved@example.com",
    confirm_text=DEFAULT_CONFIRMATION_TEXT,
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    preview=sample_preview,
    preview_source_path="preview.json",
    cc="cc@example.com",
  )
  assert result["ok"] is False
  assert result["error"] == "cc_bcc_not_allowed"


def test_send_success_with_mock_smtp(monkeypatch: pytest.MonkeyPatch, sample_preview: dict, tmp_path: Path) -> None:
  _configure_send(monkeypatch)
  calls: list[dict] = []

  def _mock_send(**kwargs: object) -> None:
    calls.append(dict(kwargs))

  user_context = {
    "user_id": "admin@example.com",
    "display_name": "Admin",
    "role": "admin",
    "auth_provider": "iap",
    "is_admin": True,
  }
  result = send_live_digest_email_to_approved_member(
    recipient="approved@example.com",
    confirm_text=DEFAULT_CONFIRMATION_TEXT,
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    preview=sample_preview,
    preview_source_path="preview.json",
    smtp_send_fn=_mock_send,
    user_context=user_context,
  )
  assert result["ok"] is True
  assert result["action_type"] == ACTION_TYPE
  assert len(calls) == 1
  assert calls[0]["recipient"] == "approved@example.com"
  assert "secret-not-real" not in json.dumps(result)
  assert Path(result["saved_paths"]["json"]).exists()

  history = list_run_history_entries(
    tmp_path,
    limit=5,
    action_type=ACTION_TYPE,
    viewer_user_context={"user_id": "admin@example.com", "role": "admin", "is_admin": True},
  )
  assert history
  assert history[0]["action_type"] == ACTION_TYPE
  assert "secret-not-real" not in json.dumps(history[0])


def test_send_log_excludes_password(tmp_path: Path) -> None:
  result = {
    "ok": True,
    "status": "sent",
    "sent_at": "2026-06-18T12:00:00+00:00",
    "recipient_email": "approved@example.com",
    "recipient_domain": "example.com",
    "preview_source_path": "preview.json",
    "send_mode": "approved_member_manual",
    "action_type": ACTION_TYPE,
    "safety_flags": {"manual_only": True},
  }
  saved = save_live_approved_member_send_log(
    result,
    subject="Subject",
    digest_preview_artifact="preview.json",
    output_root=tmp_path,
  )
  text = Path(saved["json"]).read_text(encoding="utf-8")
  assert "SMTP_PASSWORD" not in text
  assert "secret-not-real" not in text
  assert "approved@example.com" in text
