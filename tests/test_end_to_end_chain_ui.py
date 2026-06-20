"""Tests for JP seed end-to-end chain UI (Phase 24.4C)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui import theme_validation_ui


def test_ui_has_end_to_end_chain_section() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "JP Seed End-to-End Chain" in text
  assert "render_end_to_end_chain_section" in text
  assert "End-to-End状態を確認する" in text
  assert "Paper Query Planを作る" in text
  assert "Digest Previewを生成する" in text
  assert "End-to-Endレポートを保存する" in text


def test_ui_external_api_warning() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "OpenAlex/Tavily/BigQuery" in text
  assert "社外秘情報を含めない" in text
  assert "allow_external_api" in text


def test_ui_no_email_or_scheduler_buttons() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  e2e_start = text.index("def render_end_to_end_chain_section")
  e2e_block = text[e2e_start : text.index("def render_theme_validation_intro_card")]
  assert "メール送信" not in e2e_block or "outbound email" in e2e_block
  assert "scheduler" not in e2e_block.lower()
  assert "send_email" not in e2e_block
  assert "install_weekly" not in e2e_block


def test_ui_fto_caution_remains() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "FTO" in text
  assert "侵害" in text
  assert "有効性" in text
  assert callable(theme_validation_ui.render_end_to_end_chain_section)
