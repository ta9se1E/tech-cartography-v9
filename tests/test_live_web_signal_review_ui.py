"""Tests for live web signal review UI (Phase 25U)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui import live_web_signal_review_ui


def test_ui_exports() -> None:
  assert callable(live_web_signal_review_ui.render_live_web_signal_review_section)


def test_ui_has_safety_notices() -> None:
  text = Path(live_web_signal_review_ui.__file__).read_text(encoding="utf-8")
  assert "候補情報" in text
  assert "FTO" in text
  assert "smtplib" not in text
  assert "send_email" not in text
