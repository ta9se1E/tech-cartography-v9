"""Strategic Watch Brief UI tests (Phase 25V)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui import live_strategic_watch_brief_ui


def test_ui_exports() -> None:
  assert callable(live_strategic_watch_brief_ui.render_live_strategic_watch_brief_section)


def test_ui_no_external_actions() -> None:
  text = Path(live_strategic_watch_brief_ui.__file__).read_text(encoding="utf-8")
  assert "Strategic Watch Brief" in text
  assert "smtplib" not in text
  assert "deep_research" not in text.lower()
