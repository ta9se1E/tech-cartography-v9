"""Tests for email send config (Phase 25G)."""

from __future__ import annotations

import pytest

from tech_cartography.runtime.cloud_run_config import DISABLE_EMAIL_SEND_ENV
from tech_cartography.runtime.email_send_config import (
  SELF_ONLY_SEND_MODE,
  can_send_self_only_email,
  get_email_send_status,
  is_recipient_allowed,
  mask_recipient,
  missing_smtp_fields,
  parse_recipient_allowlist,
  self_only_block_message,
)


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


def test_disabled_email_send_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EMAIL_SEND_ENV, "true")
  monkeypatch.setenv("EMAIL_SEND_MODE", SELF_ONLY_SEND_MODE)
  monkeypatch.setenv("EMAIL_RECIPIENT_ALLOWLIST", "me@example.com")
  allowed, reason = can_send_self_only_email("me@example.com")
  assert allowed is False
  assert reason == "disabled_by_env"


def test_non_self_only_mode_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EMAIL_SEND_ENV, "false")
  monkeypatch.setenv("EMAIL_SEND_MODE", "broadcast")
  monkeypatch.setenv("EMAIL_RECIPIENT_ALLOWLIST", "me@example.com")
  allowed, reason = can_send_self_only_email("me@example.com")
  assert allowed is False
  assert reason == "invalid_send_mode"


def test_recipient_not_in_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EMAIL_SEND_ENV, "false")
  monkeypatch.setenv("EMAIL_SEND_MODE", SELF_ONLY_SEND_MODE)
  monkeypatch.setenv("EMAIL_RECIPIENT_ALLOWLIST", "me@example.com")
  assert is_recipient_allowed("other@example.com") is False
  allowed, reason = can_send_self_only_email("other@example.com")
  assert allowed is False
  assert reason == "recipient_not_allowed"


def test_missing_smtp_password_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EMAIL_SEND_ENV, "false")
  monkeypatch.setenv("EMAIL_SEND_MODE", SELF_ONLY_SEND_MODE)
  monkeypatch.setenv("EMAIL_RECIPIENT_ALLOWLIST", "me@example.com")
  monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
  monkeypatch.setenv("SMTP_PORT", "465")
  monkeypatch.setenv("SMTP_USERNAME", "me@example.com")
  assert "SMTP_PASSWORD" in missing_smtp_fields()
  allowed, reason = can_send_self_only_email("me@example.com")
  assert allowed is False
  assert reason == "missing_smtp_config"


def test_self_only_allowed_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EMAIL_SEND_ENV, "false")
  monkeypatch.setenv("EMAIL_SEND_MODE", SELF_ONLY_SEND_MODE)
  monkeypatch.setenv("EMAIL_RECIPIENT_ALLOWLIST", "me@example.com, other@example.com")
  monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
  monkeypatch.setenv("SMTP_PORT", "587")
  monkeypatch.setenv("SMTP_USERNAME", "me@example.com")
  monkeypatch.setenv("SMTP_PASSWORD", "secret-not-real")
  monkeypatch.setenv("EMAIL_SENDER", "me@example.com")
  allowed, reason = can_send_self_only_email("other@example.com")
  assert allowed is True
  assert reason is None
  assert parse_recipient_allowlist() == ["me@example.com", "other@example.com"]


def test_status_never_includes_password(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("SMTP_PASSWORD", "secret-not-real")
  status = get_email_send_status()
  assert "secret-not-real" not in str(status)
  assert "password" not in str(status).lower() or "missing_smtp_fields" in status


def test_mask_recipient() -> None:
  assert mask_recipient("me@example.com") == "m***@example.com"


def test_block_messages() -> None:
  assert "DISABLE_EMAIL_SEND" in self_only_block_message("disabled_by_env")
