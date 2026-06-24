"""Tests for Web Signal collection UI (Phase 25T)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui import live_web_signal_collection_ui


def test_ui_exports() -> None:
  assert callable(live_web_signal_collection_ui.render_live_web_signal_collection_section)


def test_ui_has_safety_notices() -> None:
  text = Path(live_web_signal_collection_ui.__file__).read_text(encoding="utf-8")
  assert "候補情報" in text
  assert "Web Signal候補を手動収集" in text
  assert "send_email" not in text.lower()
