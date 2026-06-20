"""Tests for email outbox (Phase 24.1)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.delivery.email_outbox import (
  STATUS_BLOCKED_MISSING_RECIPIENT,
  STATUS_DRAFT_SAVED,
  STATUS_PREVIEW_ONLY,
  build_email_draft_from_weekly_digest,
  load_email_draft,
  render_email_draft_summary_md,
  save_email_draft,
)
from tech_cartography.delivery.japanese_copy import ja_status_label
from tech_cartography.delivery.weekly_digest import WeeklyDigest


def _sample_digest() -> WeeklyDigest:
  return WeeklyDigest(
    digest_id="digest-test",
    created_at="2026-06-20T00:00:00+00:00",
    subject="[Tech Cartography] Weekly Intelligence Digest - US-1 - 2026-06-20",
    markdown_body="# Tech Cartography 週次インテリジェンスDigest\n\n## 1. 今週の差分\n",
    html_body="<html><body>digest</body></html>",
    diff_summary="初回ベースライン",
    caveats=["Webシグナルは「確認候補」であり、事実関係や特許との関係を断定するものではありません。"],
  )


def test_build_email_draft_with_recipient() -> None:
  draft = build_email_draft_from_weekly_digest(
    _sample_digest(),
    publication_number="US-1",
    to="reviewer@example.com",
    status=STATUS_DRAFT_SAVED,
  )
  assert draft.to == ["reviewer@example.com"]
  assert draft.status == STATUS_DRAFT_SAVED
  assert "1. 今週の差分" in draft.markdown_body
  assert any("確認候補" in c for c in draft.caveats)
  assert "下書き" in ja_status_label(draft.status)


def test_build_email_draft_blocked_missing_recipient_on_send() -> None:
  draft = build_email_draft_from_weekly_digest(
    _sample_digest(),
    publication_number="US-1",
    to=None,
    send_requested=True,
  )
  assert draft.status == STATUS_BLOCKED_MISSING_RECIPIENT


def test_build_email_draft_preview_only_without_recipient() -> None:
  draft = build_email_draft_from_weekly_digest(
    _sample_digest(),
    publication_number="US-1",
    to=None,
    status=STATUS_DRAFT_SAVED,
  )
  assert draft.status == STATUS_PREVIEW_ONLY


def test_save_and_load_email_draft(tmp_path: Path) -> None:
  draft = build_email_draft_from_weekly_digest(
    _sample_digest(),
    publication_number="US-12565719-B2",
    to="reviewer@example.com",
  )
  paths = save_email_draft(draft, tmp_path)
  assert paths["email_draft_json"].exists()
  assert paths["email_draft_md"].exists()
  assert paths["email_draft_html"].exists()
  assert paths["outbox_index"].exists()

  loaded = load_email_draft(paths["email_draft_json"])
  assert loaded is not None
  assert loaded.draft_id == draft.draft_id
  assert loaded.to == ["reviewer@example.com"]


def test_email_draft_summary_md_japanese_status() -> None:
  draft = build_email_draft_from_weekly_digest(
    _sample_digest(),
    publication_number="US-1",
    to="reviewer@example.com",
    status=STATUS_DRAFT_SAVED,
  )
  summary = render_email_draft_summary_md(draft)
  assert "メール下書き" in summary
  assert "下書き保存済み" in summary
  assert "週次インテリジェンスDigestの下書き" in draft.markdown_body
