"""Tests for optional SMTP sender (Phase 24.1 / 24.2)."""

from __future__ import annotations

from unittest.mock import patch

from tech_cartography.delivery.email_outbox import (
  STATUS_BLOCKED_MISSING_ADAPTER,
  STATUS_BLOCKED_MISSING_RECIPIENT,
  build_email_draft_from_weekly_digest,
)
from tech_cartography.delivery.email_sender import (
  can_send_email,
  format_smtp_missing_message,
  resolve_smtp_settings,
  send_email_smtp,
)
from tech_cartography.delivery.weekly_digest import WeeklyDigest

_ALL_SMTP_KEYS = (
  "TC_SMTP_HOST",
  "TC_SMTP_PORT",
  "TC_SMTP_USER",
  "TC_SMTP_PASSWORD",
  "TC_SMTP_FROM",
  "SMTP_HOST",
  "SMTP_PORT",
  "SMTP_USER",
  "SMTP_PASSWORD",
  "SMTP_FROM",
  "SMTP_FROM_EMAIL",
)


def _clear_smtp_env(monkeypatch) -> None:
  for key in _ALL_SMTP_KEYS:
    monkeypatch.delenv(key, raising=False)


def _set_smtp_only(monkeypatch) -> None:
  _clear_smtp_env(monkeypatch)
  monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
  monkeypatch.setenv("SMTP_PORT", "587")
  monkeypatch.setenv("SMTP_USER", "user@gmail.com")
  monkeypatch.setenv("SMTP_PASSWORD", "secret-app-password")
  monkeypatch.setenv("SMTP_FROM_EMAIL", "user@gmail.com")


def _sample_draft(*, to: str | None = "reviewer@example.com"):
  digest = WeeklyDigest(
    digest_id="d1",
    created_at="2026-06-20T00:00:00+00:00",
    subject="Test",
    markdown_body="body",
    html_body="<p>body</p>",
    diff_summary="",
  )
  return build_email_draft_from_weekly_digest(
    digest,
    publication_number="US-1",
    to=to,
  )


def test_resolve_smtp_settings_supports_smtp_only(monkeypatch) -> None:
  _set_smtp_only(monkeypatch)
  settings = resolve_smtp_settings()
  assert settings["host"] == "smtp.gmail.com"
  assert settings["port"] == "587"
  assert settings["user"] == "user@gmail.com"
  assert settings["password"] == "secret-app-password"
  assert settings["from_email"] == "user@gmail.com"
  assert settings["source"]["host"] == "SMTP_HOST"
  assert settings["source"]["password"] == "SMTP_PASSWORD"


def test_resolve_smtp_settings_tc_prefers_tc_over_smtp(monkeypatch) -> None:
  _set_smtp_only(monkeypatch)
  monkeypatch.setenv("TC_SMTP_HOST", "tc.example.com")
  monkeypatch.setenv("TC_SMTP_PORT", "2525")
  monkeypatch.setenv("TC_SMTP_USER", "tc-user")
  monkeypatch.setenv("TC_SMTP_PASSWORD", "tc-secret")
  monkeypatch.setenv("TC_SMTP_FROM", "tc-from@example.com")
  settings = resolve_smtp_settings()
  assert settings["host"] == "tc.example.com"
  assert settings["source"]["host"] == "TC_SMTP_HOST"
  assert settings["from_email"] == "tc-from@example.com"


def test_resolve_smtp_settings_from_email_falls_back_to_smtp_user(monkeypatch) -> None:
  _clear_smtp_env(monkeypatch)
  monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
  monkeypatch.setenv("SMTP_PORT", "587")
  monkeypatch.setenv("SMTP_USER", "fallback@gmail.com")
  monkeypatch.setenv("SMTP_PASSWORD", "secret")
  settings = resolve_smtp_settings()
  assert settings["from_email"] == "fallback@gmail.com"
  assert settings["source"]["from_email"] == "SMTP_USER"


def test_can_send_email_true_with_smtp_only(monkeypatch) -> None:
  _set_smtp_only(monkeypatch)
  ready, reason = can_send_email()
  assert ready is True
  assert "利用可能" in reason


def test_can_send_email_missing_env_japanese_message(monkeypatch) -> None:
  _clear_smtp_env(monkeypatch)
  ready, reason = can_send_email()
  assert ready is False
  assert "SMTP設定が不足しています" in reason
  assert "SMTP_HOST または TC_SMTP_HOST" in reason
  assert "secret-app-password" not in reason
  assert "SMTP_PASSWORD(非表示)" in reason or "password" in reason


def test_format_smtp_missing_message_masks_password_label() -> None:
  message = format_smtp_missing_message(["password"])
  assert "SMTP_PASSWORD(非表示)" in message


def test_send_email_blocked_missing_recipient() -> None:
  draft = _sample_draft(to=None)
  result = send_email_smtp(draft)
  assert result["ok"] is False
  assert result["status"] == STATUS_BLOCKED_MISSING_RECIPIENT


def test_send_email_blocked_missing_adapter(monkeypatch) -> None:
  _clear_smtp_env(monkeypatch)
  draft = _sample_draft()
  result = send_email_smtp(draft)
  assert result["ok"] is False
  assert result["status"] == STATUS_BLOCKED_MISSING_ADAPTER
  assert "SMTP設定が不足しています" in result["message"]


def test_send_email_not_called_without_flag_in_store(monkeypatch, tmp_path) -> None:
  from tests.test_digest_diff import _write_snapshot_fixture
  from tech_cartography.delivery.store import build_delivery_package

  _write_snapshot_fixture(tmp_path)
  with patch("tech_cartography.delivery.store.send_email_smtp") as mock_send:
    build_delivery_package(
      "US-12565719-B2",
      project_root=tmp_path,
      output_dir=tmp_path / "outputs" / "delivery",
      build_email_draft=True,
      email_to="reviewer@example.com",
      send_email=False,
    )
    mock_send.assert_not_called()
