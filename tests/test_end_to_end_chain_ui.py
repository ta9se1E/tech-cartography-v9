"""Tests for JP seed end-to-end chain UI (Phase 24.4C / 24.4C.1)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui import theme_validation_ui

UI_PATH = Path("src/tech_cartography/ui/theme_validation_ui.py")


def _section_text(start: str, end: str) -> str:
  text = UI_PATH.read_text(encoding="utf-8")
  return text.split(start, 1)[1].split(end, 1)[0]


def test_ui_has_end_to_end_chain_section() -> None:
  text = UI_PATH.read_text(encoding="utf-8")
  assert "JP Seed End-to-End Chain" in text
  assert "最後までつなぐ検証" in text
  assert "render_end_to_end_chain_section" in text
  assert "End-to-End状態を確認する" in text
  assert "Paper Query Planを作る" in text
  assert "Digest Previewを生成する" in text
  assert "End-to-Endレポートを保存する" in text


def _analyst_section_text(start: str, end: str) -> str:
  text = UI_PATH.read_text(encoding="utf-8")
  return text.split(start, 1)[1].split(end, 1)[0]


def test_render_theme_validation_section_calls_end_to_end_chain() -> None:
  section = _analyst_section_text("def render_analyst_input_execution_section", "def render_theme_validation_section")
  evidence_idx = section.index("render_evidence_map_builder")
  e2e_idx = section.index("render_end_to_end_chain_section")
  assert evidence_idx < e2e_idx
  assert section.count("render_end_to_end_chain_section") == 1


def test_end_to_end_chain_after_evidence_map_builder() -> None:
  section = _analyst_section_text("def render_analyst_input_execution_section", "def render_theme_validation_section")
  assert "render_evidence_map_builder" in section
  assert section.index("render_evidence_map_builder") < section.index("render_end_to_end_chain_section")


def test_seed_empty_shows_heading_and_info() -> None:
  e2e = _section_text("def render_end_to_end_chain_section", "def render_theme_validation_intro_card")
  assert "JP Seed End-to-End Chain / 最後までつなぐ検証" in e2e
  assert "seed publication numbersを入力してください" in e2e
  assert "if not seeds_ready:" in e2e
  assert "st.divider()" in e2e


def test_seed_present_shows_multiselect_and_defaults() -> None:
  e2e = _section_text("def render_end_to_end_chain_section", "def render_theme_validation_intro_card")
  assert "st.multiselect" in e2e
  assert "default=default_selection" in e2e
  assert 'options=seeds' in e2e
  assert 'value=True' in e2e and "dry_run" in e2e
  assert 'value=False' in e2e
  assert "run_openalex" in e2e
  assert "run_tavily" in e2e
  assert "run_bigquery" in e2e
  assert "allow_external_api" in e2e


def test_ui_external_api_warning() -> None:
  e2e = _section_text("def render_end_to_end_chain_section", "def render_theme_validation_intro_card")
  assert "OpenAlex/Tavily/BigQuery" in e2e
  assert "社外秘情報を含めない" in e2e


def test_ui_no_email_or_scheduler_buttons() -> None:
  e2e = _section_text("def render_end_to_end_chain_section", "def render_theme_validation_intro_card")
  assert "scheduler" not in e2e.lower()
  assert "send_email" not in e2e
  assert "install_weekly" not in e2e


def test_ui_fto_caution_remains() -> None:
  text = UI_PATH.read_text(encoding="utf-8")
  assert "FTO" in text
  assert "侵害" in text
  assert "有効性" in text
  assert callable(theme_validation_ui.render_end_to_end_chain_section)


def test_intro_lines_present() -> None:
  text = UI_PATH.read_text(encoding="utf-8")
  assert "END_TO_END_INTRO_LINES" in text
  assert "Stage 4以降" in text
  assert "外部APIは明示同意" in text
