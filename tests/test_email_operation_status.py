"""Tests for email operation status (Phase 25Q.2)."""

from __future__ import annotations

import json

import pytest

from tech_cartography.runtime.approved_member_send_config import (
  APPROVED_MEMBER_EMAILS_ENV,
  ENABLE_APPROVED_MEMBER_SEND_ENV,
)
from tech_cartography.runtime.cloud_run_config import (
  DISABLE_EMAIL_SEND_ENV,
  DISABLE_SCHEDULER_ENV,
)
from tech_cartography.runtime.email_operation_status import (
  SAFETY_LEVEL_CONTROLLED,
  SAFETY_LEVEL_MISCONFIGURED,
  SAFETY_LEVEL_RISKY,
  SAFETY_LEVEL_SAFE_OFF,
  build_post_send_reset_command,
  get_email_operation_status,
)
from tech_cartography.runtime.email_send_config import (
  SMTP_HOST_ENV,
  SMTP_PASSWORD_ENV,
  SMTP_PORT_ENV,
  SMTP_USERNAME_ENV,
)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  for name in (
    DISABLE_EMAIL_SEND_ENV,
    ENABLE_APPROVED_MEMBER_SEND_ENV,
    APPROVED_MEMBER_EMAILS_ENV,
    DISABLE_SCHEDULER_ENV,
    "AUTH_PROVIDER_MODE",
    "EMAIL_SEND_MODE",
    "EMAIL_RECIPIENT_ALLOWLIST",
    SMTP_HOST_ENV,
    SMTP_PORT_ENV,
    SMTP_USERNAME_ENV,
    SMTP_PASSWORD_ENV,
  ):
    monkeypatch.delenv(name, raising=False)
  monkeypatch.setenv(DISABLE_EMAIL_SEND_ENV, "true")
  monkeypatch.setenv(ENABLE_APPROVED_MEMBER_SEND_ENV, "false")
  monkeypatch.setenv(DISABLE_SCHEDULER_ENV, "true")


def test_default_is_safe_off() -> None:
  status = get_email_operation_status()
  assert status["safety_level"] == SAFETY_LEVEL_SAFE_OFF
  assert status["email_send_disabled"] is True
  assert status["approved_member_send_enabled"] is False


def test_disable_email_send_is_safe_off(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EMAIL_SEND_ENV, "true")
  monkeypatch.setenv(ENABLE_APPROVED_MEMBER_SEND_ENV, "true")
  status = get_email_operation_status()
  assert status["safety_level"] == SAFETY_LEVEL_SAFE_OFF


def test_controlled_manual_send_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EMAIL_SEND_ENV, "false")
  monkeypatch.setenv(ENABLE_APPROVED_MEMBER_SEND_ENV, "true")
  monkeypatch.setenv(APPROVED_MEMBER_EMAILS_ENV, "approved@example.com")
  monkeypatch.setenv(DISABLE_SCHEDULER_ENV, "true")
  monkeypatch.setenv("AUTH_PROVIDER_MODE", "iap")
  monkeypatch.setenv(SMTP_HOST_ENV, "smtp.example.com")
  monkeypatch.setenv(SMTP_PORT_ENV, "465")
  monkeypatch.setenv(SMTP_USERNAME_ENV, "sender@example.com")
  monkeypatch.setenv(SMTP_PASSWORD_ENV, "secret-not-real")
  status = get_email_operation_status()
  assert status["safety_level"] == SAFETY_LEVEL_CONTROLLED
  assert status["approved_member_count"] == 1


def test_scheduler_enabled_is_risky(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EMAIL_SEND_ENV, "false")
  monkeypatch.setenv(DISABLE_SCHEDULER_ENV, "false")
  monkeypatch.setenv(SMTP_HOST_ENV, "smtp.example.com")
  monkeypatch.setenv(SMTP_PORT_ENV, "465")
  monkeypatch.setenv(SMTP_USERNAME_ENV, "sender@example.com")
  monkeypatch.setenv(SMTP_PASSWORD_ENV, "secret-not-real")
  status = get_email_operation_status()
  assert status["safety_level"] == SAFETY_LEVEL_RISKY


def test_smtp_missing_is_misconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EMAIL_SEND_ENV, "false")
  monkeypatch.setenv(ENABLE_APPROVED_MEMBER_SEND_ENV, "true")
  monkeypatch.setenv(APPROVED_MEMBER_EMAILS_ENV, "approved@example.com")
  monkeypatch.setenv(DISABLE_SCHEDULER_ENV, "true")
  status = get_email_operation_status()
  assert status["safety_level"] == SAFETY_LEVEL_MISCONFIGURED


def test_does_not_return_smtp_password_value(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(SMTP_PASSWORD_ENV, "super-secret-password-value")
  status = get_email_operation_status()
  serialized = json.dumps(status)
  assert "super-secret-password-value" not in serialized
  assert "smtp_password_configured" in serialized


def test_reset_command_has_no_secrets() -> None:
  command = build_post_send_reset_command()
  assert "SMTP_PASSWORD" not in command
  assert "ENABLE_APPROVED_MEMBER_SEND=false" in command
  assert "DISABLE_EMAIL_SEND=true" in command
