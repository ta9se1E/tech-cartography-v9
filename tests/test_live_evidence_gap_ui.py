"""Evidence Gap UI tests (Phase 25V)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui import live_evidence_gap_ui


def test_ui_exports() -> None:
  assert callable(live_evidence_gap_ui.render_live_evidence_gap_section)


def test_ui_safety() -> None:
  text = Path(live_evidence_gap_ui.__file__).read_text(encoding="utf-8")
  assert "候補" in text
  assert "FTO" in text or "法的" in text
  assert "send_email" not in text
  assert "collect_live_web_signals" not in text
