"""Tests for approved member send config (Phase 25Q)."""

from __future__ import annotations

import pytest

from tech_cartography.runtime.approved_member_send_config import (
  APPROVED_MEMBER_EMAILS_ENV,
  DEFAULT_CONFIRMATION_TEXT,
  ENABLE_APPROVED_MEMBER_SEND_ENV,
  can_send_approved_member_email,
  get_confirmation_text,
  is_approved_member_recipient,
  is_approved_member_send_enabled,
  parse_approved_member_emails,
)
from tech_cartography.runtime.cloud_run_config import DISABLE_EMAIL_SEND_ENV


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  for name in (
    ENABLE_APPROVED_MEMBER_SEND_ENV,
    APPROVED_MEMBER_EMAILS_ENV,
    "APPROVED_MEMBER_SEND_CONFIRMATION",
    DISABLE_EMAIL_SEND_ENV,
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
  ):
    monkeypatch.delenv(name, raising=False)


def test_default_disabled() -> None:
  assert is_approved_member_send_enabled() is False
  allowed, reason = can_send_approved_member_email("approved@example.com")
  assert allowed is False
  assert reason == "approved_member_send_disabled"


def test_disable_email_send_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(ENABLE_APPROVED_MEMBER_SEND_ENV, "true")
  monkeypatch.setenv(APPROVED_MEMBER_EMAILS_ENV, "approved@example.com")
  monkeypatch.setenv(DISABLE_EMAIL_SEND_ENV, "true")
  allowed, reason = can_send_approved_member_email("approved@example.com")
  assert allowed is False
  assert reason == "disabled_by_env"


def test_empty_approved_list_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(ENABLE_APPROVED_MEMBER_SEND_ENV, "true")
  monkeypatch.setenv(DISABLE_EMAIL_SEND_ENV, "false")
  allowed, reason = can_send_approved_member_email("approved@example.com")
  assert allowed is False
  assert reason == "approved_list_empty"


def test_parse_normalizes_and_dedupes(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(
    APPROVED_MEMBER_EMAILS_ENV,
    " Approved@Example.com ,approved@example.com, bad-email ",
  )
  assert parse_approved_member_emails() == ["approved@example.com"]


def test_only_approved_recipient_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(ENABLE_APPROVED_MEMBER_SEND_ENV, "true")
  monkeypatch.setenv(DISABLE_EMAIL_SEND_ENV, "false")
  monkeypatch.setenv(APPROVED_MEMBER_EMAILS_ENV, "approved@example.com")
  monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
  monkeypatch.setenv("SMTP_PORT", "465")
  monkeypatch.setenv("SMTP_USERNAME", "sender@example.com")
  monkeypatch.setenv("SMTP_PASSWORD", "secret-not-real")

  assert is_approved_member_recipient("approved@example.com") is True
  allowed, reason = can_send_approved_member_email("approved@example.com")
  assert allowed is True
  assert reason is None

  allowed_other, other_reason = can_send_approved_member_email("other@example.com")
  assert allowed_other is False
  assert other_reason == "recipient_not_approved"


def test_confirmation_text_default() -> None:
  assert get_confirmation_text() == DEFAULT_CONFIRMATION_TEXT
