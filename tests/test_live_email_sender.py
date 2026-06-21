"""Tests for live email sender (Phase 25G)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tech_cartography.runtime.cloud_run_config import DISABLE_EMAIL_SEND_ENV
from tech_cartography.runtime.email_send_config import SELF_ONLY_SEND_MODE
from tech_cartography.services.live_email_sender import (
  CONFIRMATION_TEXT,
  LIVE_EMAIL_SAFETY_NOTICE,
  build_outbound_body,
  save_live_email_send_log,
  send_live_digest_email_self_only,
)


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
    DISABLE_EMAIL_SEND_ENV,
    "EMAIL_SEND_MODE",
    "EMAIL_RECIPIENT_ALLOWLIST",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "EMAIL_SENDER",
  ):
    monkeypatch.delenv(name, raising=False)


def _configure_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EMAIL_SEND_ENV, "false")
  monkeypatch.setenv("EMAIL_SEND_MODE", SELF_ONLY_SEND_MODE)
  monkeypatch.setenv("EMAIL_RECIPIENT_ALLOWLIST", "me@example.com")
  monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
  monkeypatch.setenv("SMTP_PORT", "465")
  monkeypatch.setenv("SMTP_USERNAME", "me@example.com")
  monkeypatch.setenv("SMTP_PASSWORD", "secret-not-real")
  monkeypatch.setenv("EMAIL_SENDER", "me@example.com")


def test_build_outbound_body_includes_safety_notice(sample_preview: dict) -> None:
  body = build_outbound_body(plain_text_body=str(sample_preview["body"]))
  assert "Live Digest Preview" in body
  assert "Web Signal" in body
  assert "FTO" in body


def test_send_blocked_when_disabled(monkeypatch: pytest.MonkeyPatch, sample_preview: dict, tmp_path: Path) -> None:
  monkeypatch.setenv(DISABLE_EMAIL_SEND_ENV, "true")
  monkeypatch.setenv("EMAIL_SEND_MODE", SELF_ONLY_SEND_MODE)
  monkeypatch.setenv("EMAIL_RECIPIENT_ALLOWLIST", "me@example.com")
  result = send_live_digest_email_self_only(
    recipient="me@example.com",
    confirm_text=CONFIRMATION_TEXT,
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    preview=sample_preview,
    preview_source_path="preview.json",
  )
  assert result["ok"] is False
  assert result["status"] == "disabled_by_env"


def test_send_blocked_on_confirm_text_mismatch(monkeypatch: pytest.MonkeyPatch, sample_preview: dict, tmp_path: Path) -> None:
  _configure_smtp(monkeypatch)
  result = send_live_digest_email_self_only(
    recipient="me@example.com",
    confirm_text="WRONG",
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    preview=sample_preview,
    preview_source_path="preview.json",
  )
  assert result["ok"] is False
  assert result["status"] == "confirm_text_mismatch"


def test_send_success_with_mock_smtp(monkeypatch: pytest.MonkeyPatch, sample_preview: dict, tmp_path: Path) -> None:
  _configure_smtp(monkeypatch)
  calls: list[dict] = []

  def _mock_send(**kwargs: object) -> None:
    calls.append(dict(kwargs))

  result = send_live_digest_email_self_only(
    recipient="me@example.com",
    confirm_text=CONFIRMATION_TEXT,
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    preview=sample_preview,
    preview_source_path="preview.json",
    smtp_send_fn=_mock_send,
  )
  assert result["ok"] is True
  assert result["send_mode"] == "self_only"
  assert result["recipient_masked"] == "m***@example.com"
  assert len(calls) == 1
  assert calls[0]["recipient"] == "me@example.com"
  assert "secret-not-real" not in json.dumps(result)
  assert LIVE_EMAIL_SAFETY_NOTICE.split()[0] in calls[0]["body"]
  assert Path(result["saved_paths"]["json"]).exists()


def test_send_log_excludes_password(tmp_path: Path) -> None:
  result = {
    "ok": True,
    "status": "sent",
    "sent_at": "2026-06-18T12:00:00+00:00",
    "recipient_masked": "m***@example.com",
    "provider": "smtp",
    "preview_source_path": "preview.json",
    "send_mode": "self_only",
  }
  saved = save_live_email_send_log(result, subject="Subject", output_root=tmp_path)
  text = Path(saved["json"]).read_text(encoding="utf-8")
  assert "SMTP_PASSWORD" not in text
  assert "secret-not-real" not in text


def test_send_blocked_for_non_admin(monkeypatch: pytest.MonkeyPatch, sample_preview: dict, tmp_path: Path) -> None:
  _configure_smtp(monkeypatch)
  result = send_live_digest_email_self_only(
    recipient="me@example.com",
    confirm_text=CONFIRMATION_TEXT,
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="member",
    preview=sample_preview,
    preview_source_path="preview.json",
  )
  assert result["ok"] is False
  assert result["status"] == "admin_required"
