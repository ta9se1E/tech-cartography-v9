"""Weekly Decision Cockpit UI tests (Phase 25W)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui import live_weekly_decision_cockpit_ui


def test_ui_exports() -> None:
  assert callable(live_weekly_decision_cockpit_ui.render_live_weekly_decision_cockpit_section)


def test_ui_safety_and_tabs() -> None:
  text = Path(live_weekly_decision_cockpit_ui.__file__).read_text(encoding="utf-8")
  assert "候補情報" in text
  assert "FTO" in text
  assert "send_email" not in text
  assert "collect_live_web_signals" not in text
  app_text = Path("src/tech_cartography/ui/v7_easy_app.py").read_text(encoding="utf-8")
  assert "weekly_decision" in app_text
  assert "今週の判断" in Path("src/tech_cartography/ui/japanese_labels.py").read_text(encoding="utf-8")
