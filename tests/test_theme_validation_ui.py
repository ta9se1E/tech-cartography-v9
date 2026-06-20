"""Tests for theme validation Streamlit UI helpers (Phase 24.4A)."""

from __future__ import annotations

from tech_cartography.ui import theme_validation_ui
from tech_cartography.validation.theme_validation import THEME_VALIDATION_SAFETY_MESSAGES


def test_safety_messages_cover_fto_and_external_api() -> None:
  joined = "\n".join(THEME_VALIDATION_SAFETY_MESSAGES)
  assert "FTO" in joined
  assert "侵害" in joined
  assert "有効性" in joined
  assert "外部API" in joined or "BigQuery" in joined
  assert "社外秘" in joined


def test_ui_module_exports_render_functions() -> None:
  assert callable(theme_validation_ui.render_theme_validation_section)
  assert callable(theme_validation_ui.render_theme_validation_intro_card)
  assert callable(theme_validation_ui.render_theme_validation_safety_messages)


def test_ui_safety_renderer_uses_shared_messages() -> None:
  assert len(THEME_VALIDATION_SAFETY_MESSAGES) >= 5
  assert "最終結論ではありません" in THEME_VALIDATION_SAFETY_MESSAGES[3]
