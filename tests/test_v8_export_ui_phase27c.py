"""Tests for v8 export UI phase 27C."""

from __future__ import annotations

from pathlib import Path

import tech_cartography.ui.v8_export_ui as export_ui


def test_v8_export_ui_has_package_controls() -> None:
  text = Path(export_ui.__file__).read_text(encoding="utf-8")
  assert "Export Package" in text
  assert "manifest" in text
  assert "FTO" in text
  assert "SMTP_PASSWORD" not in text
  assert "use_container_width" not in text


def test_v8_export_ui_importable() -> None:
  assert callable(export_ui.render_v8_export_tab)
