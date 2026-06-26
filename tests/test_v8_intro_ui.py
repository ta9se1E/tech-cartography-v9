"""Tests for v8 intro UI (Phase 27B)."""

from __future__ import annotations

from pathlib import Path

import tech_cartography.ui.v8_intro_ui as intro_ui


def test_v8_intro_has_render_function() -> None:
  assert callable(intro_ui.render_v8_intro_tab)


def test_v8_intro_module_content() -> None:
  text = Path(intro_ui.__file__).read_text(encoding="utf-8")
  assert "FTO" in text
  assert "侵害" in text
  assert "定点観測" in text
  assert "V8_TAB_LABELS" in text
