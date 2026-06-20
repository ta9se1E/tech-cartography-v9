"""Tests for theme validation Streamlit UI helpers (Phase 24.4A)."""

from __future__ import annotations

from pathlib import Path

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


def test_ui_has_manual_claims_editor_labels() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  for label in (
    "Manual Claims入力 / Manual Claims Editor",
    "claims_text",
    "source_url",
    "Manual Claimsを保存する",
    "保存後に既存outputs検証を再実行する",
    "保存用テーマID",
  ):
    assert label in text
