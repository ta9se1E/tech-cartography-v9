"""Tests for v8 intro UI (Phase 27B / 27R.2)."""

from __future__ import annotations

from pathlib import Path

import tech_cartography.ui.v8_intro_ui as intro_ui


def test_v8_intro_has_render_function() -> None:
  assert callable(intro_ui.render_v8_intro_tab)


def test_v8_intro_module_content() -> None:
  text = Path(intro_ui.__file__).read_text(encoding="utf-8")
  assert "render_judge_three_minute_guide" in text
  assert "INTRO_SAFETY_NOTICES" in text
  assert "成果ファネル" in text
  assert "Deep Research" not in text
