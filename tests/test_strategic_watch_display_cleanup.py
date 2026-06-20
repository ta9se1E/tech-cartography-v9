"""Tests for Strategic Watch compact display (Phase 24.5F)."""

from __future__ import annotations

from pathlib import Path

SW_UI = Path("src/tech_cartography/ui/strategic_watch_ui.py")
V7_EASY_APP = Path("src/tech_cartography/ui/v7_easy_app.py")


def test_normal_section_uses_compact_brief() -> None:
  text = SW_UI.read_text(encoding="utf-8")
  section = text.split("def render_strategic_watch_section", 1)[1]
  assert "render_strategic_watch_brief_compact" in section
  assert "developer_mode:" in section
  compact_block = section.split("else:", 1)[1].split("st.markdown(", 1)[0]
  assert "render_national_project_money_signals" not in compact_block
  assert "render_strategic_watch_brief_markdown" not in compact_block


def test_compact_brief_has_summary_expander_and_download() -> None:
  text = SW_UI.read_text(encoding="utf-8")
  compact = text.split("def render_strategic_watch_brief_compact", 1)[1].split(
    "def render_strategic_watch_brief_markdown",
    1,
  )[0]
  assert "STRATEGIC_WATCH_BRIEF_SUMMARY_JA" in compact
  assert "Strategic Watch Brief全文を表示" in compact
  assert "st.download_button" in compact
  assert "expanded=False" in compact


def test_developer_mode_keeps_full_sections() -> None:
  text = SW_UI.read_text(encoding="utf-8")
  section = text.split("if developer_mode:", 1)[1].split("else:", 1)[0]
  assert "render_national_project_money_signals" in section
  assert "render_strategic_watch_brief_markdown" in section


def test_market_tab_passes_developer_mode_flag() -> None:
  text = V7_EASY_APP.read_text(encoding="utf-8")
  market = text.split("def _tab_market", 1)[1].split("def _tab_analyst_input", 1)[0]
  assert "render_strategic_watch_section(strategic_watch_artifacts, developer_mode=" in market
