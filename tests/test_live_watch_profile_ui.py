"""Tests for Live Watch Profile UI (Phase 25S)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui import live_watch_profile_ui


def test_ui_module_exports_render_section() -> None:
  assert callable(live_watch_profile_ui.render_live_watch_profile_section)
  assert callable(live_watch_profile_ui.should_show_live_watch_profile_ui)


def test_ui_source_contains_safety_notices() -> None:
  text = Path(live_watch_profile_ui.__file__).read_text(encoding="utf-8")
  assert "外部検索は実行しません" in text
  assert "Schedulerは起動しません" in text
  assert "メール送信は行いません" in text
