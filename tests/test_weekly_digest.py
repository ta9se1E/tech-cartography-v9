"""Tests for weekly digest preview (Phase 24.0)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.delivery.digest_diff import DigestDiff, WeeklyDigestSnapshot
from tech_cartography.delivery.weekly_digest import (
  PREVIEW_ONLY_NOTICE,
  build_weekly_digest,
  markdown_to_simple_html,
)
from tests.test_digest_diff import _write_snapshot_fixture


def test_weekly_digest_initial(tmp_path: Path) -> None:
  _write_snapshot_fixture(tmp_path)
  diff = DigestDiff(is_initial=True, added_watch_items=["watch-1"])
  digest = build_weekly_digest("US-12565719-B2", tmp_path, diff=diff)
  assert "今週の差分" in digest.markdown_body
  assert PREVIEW_ONLY_NOTICE in digest.markdown_body
  assert digest.send_status == "preview_only"


def test_weekly_digest_has_top_watch_section(tmp_path: Path) -> None:
  _write_snapshot_fixture(tmp_path)
  digest = build_weekly_digest("US-12565719-B2", tmp_path, diff=DigestDiff(is_initial=True))
  assert "今週の重点監視候補 Top 3" in digest.markdown_body


def test_weekly_digest_html_preview() -> None:
  html = markdown_to_simple_html("# Title\n\n- item")
  assert "<html>" in html
  assert PREVIEW_ONLY_NOTICE in html
  assert "<h1>" in html


def test_email_sending_disabled_notice() -> None:
  digest = build_weekly_digest("US-X", Path("/nonexistent"), diff=DigestDiff(is_initial=True))
  assert "preview_only" in digest.send_status
  assert "Email sending is disabled" in digest.markdown_body
  assert "FTO" in digest.markdown_body or "侵害" in digest.markdown_body
