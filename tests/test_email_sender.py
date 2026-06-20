"""Tests for optional SMTP sender (Phase 24.1)."""

from __future__ import annotations

import os
from unittest.mock import patch

from tech_cartography.delivery.email_outbox import (
  STATUS_BLOCKED_MISSING_ADAPTER,
  STATUS_BLOCKED_MISSING_RECIPIENT,
  build_email_draft_from_weekly_digest,
)
from tech_cartography.delivery.email_sender import can_send_email, send_email_smtp
from tech_cartography.delivery.weekly_digest import WeeklyDigest


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


def test_can_send_email_missing_env(monkeypatch) -> None:
  for key in ("TC_SMTP_HOST", "TC_SMTP_PORT", "TC_SMTP_USER", "TC_SMTP_PASSWORD", "TC_SMTP_FROM"):
    monkeypatch.delenv(key, raising=False)
  ready, reason = can_send_email()
  assert ready is False
  assert "SMTP not configured" in reason
  assert "secret" not in reason.lower()


def test_send_email_blocked_missing_recipient() -> None:
  draft = _sample_draft(to=None)
  result = send_email_smtp(draft)
  assert result["ok"] is False
  assert result["status"] == STATUS_BLOCKED_MISSING_RECIPIENT


def test_send_email_blocked_missing_adapter(monkeypatch) -> None:
  for key in ("TC_SMTP_HOST", "TC_SMTP_PORT", "TC_SMTP_USER", "TC_SMTP_PASSWORD", "TC_SMTP_FROM"):
    monkeypatch.delenv(key, raising=False)
  draft = _sample_draft()
  result = send_email_smtp(draft)
  assert result["ok"] is False
  assert result["status"] == STATUS_BLOCKED_MISSING_ADAPTER


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
