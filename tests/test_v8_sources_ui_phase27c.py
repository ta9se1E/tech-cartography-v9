"""Tests for v8 sources UI phase 27C."""

from __future__ import annotations

from pathlib import Path

import tech_cartography.ui.v8_sources_ui as sources_ui


def test_v8_sources_ui_has_export_controls() -> None:
  text = Path(sources_ui.__file__).read_text(encoding="utf-8")
  assert "Export Package" in text
  assert "CSV" in text
  assert "Markdown" in text
  assert "width=\"stretch\"" in text
  assert "use_container_width" not in text
  assert "candidate_information_only" in text


def test_v8_sources_ui_importable() -> None:
  assert callable(sources_ui.render_v8_sources_tab)
