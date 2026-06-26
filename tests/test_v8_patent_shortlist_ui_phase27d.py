"""Tests for v8 patent shortlist UI phase 27D."""

from __future__ import annotations

from pathlib import Path

import tech_cartography.ui.v8_patent_shortlist_ui as shortlist_ui


def test_v8_patent_shortlist_ui_phase27d_controls() -> None:
  text = Path(shortlist_ui.__file__).read_text(encoding="utf-8")
  assert "Generate / Refresh Patent Shortlist" in text
  assert "width=\"stretch\"" in text
  assert "use_container_width" not in text
  assert "読む優先度" in text
  assert "FTO" in text
  assert "claim_map" in text or "Claim Map" in text
  assert "All cases" in text


def test_v8_patent_shortlist_ui_importable() -> None:
  assert callable(shortlist_ui.render_v8_patent_shortlist_tab)
