"""Tests for Study Demo Simple Mode UI."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services_v9.signal_models import Signal
from services_v9.study_demo_saved_theme_editor import apply_editor_selection_metadata, theme_to_editor_values
from services_v9.study_demo_simple_ui_analysis import (
  analyze_signal_visibility,
  analyze_simple_source_layout,
  build_simple_ui_check_result,
)
from services_v9.study_demo_ui_mode import (
  is_advanced_mode,
  is_simple_mode,
  is_study_demo_simple_ui,
  resolve_ui_mode,
  should_show_legacy_tools,
  should_show_technical_ids,
)
from ui_v9.study_demo_simple_signals_ui import filter_signals_for_simple_display, split_top_and_remaining

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "study_demo_p0_watch_profile_samples.json"
ROOT = Path(__file__).resolve().parents[1]


def _load_fixture() -> dict:
  return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _signals_with_empty_title() -> list[Signal]:
  signals = []
  for index in range(15):
    title = "" if index == 14 else f"signal {index}"
    signals.append(
      Signal.from_dict(
        {
          "id": f"sig-{index}",
          "type": "patent",
          "title": title,
          "score": 1.0 - index * 0.01,
          "status": "Stable",
          "action": "Read Now",
          "why_read": "why",
          "what_to_check": "check",
          "next_action": "act",
          "source_name": "src",
          "published_date": "2026-01-01",
          "tags": [],
          "companies": [],
        }
      )
    )
  return signals


class TestUiMode:
  def test_default_mode_is_simple(self) -> None:
    assert resolve_ui_mode({}) == "simple"
    assert is_simple_mode({}) is True

  def test_advanced_mode_switch(self) -> None:
    assert resolve_ui_mode({"V9_UI_MODE": "advanced"}) == "advanced"
    assert is_advanced_mode({"V9_UI_MODE": "advanced"}) is True

  def test_study_demo_simple_ui_requires_both_flags(self) -> None:
    env = {"V9_STUDY_DEMO_MODE": "true", "V9_UI_MODE": "simple"}
    assert is_study_demo_simple_ui(env) is True
    assert is_study_demo_simple_ui({"V9_STUDY_DEMO_MODE": "true", "V9_UI_MODE": "advanced"}) is False

  def test_technical_ids_hidden_in_simple(self) -> None:
    assert should_show_technical_ids({}) is False
    assert should_show_technical_ids({"V9_UI_MODE": "advanced"}) is True

  def test_legacy_hidden_in_simple(self) -> None:
    assert should_show_legacy_tools({}) is False
    assert should_show_legacy_tools({"V9_UI_MODE": "advanced"}) is True


class TestCompactLayout:
  def test_compact_header_once(self) -> None:
    source = (ROOT / "ui_v9/signal_watch_app.py").read_text(encoding="utf-8")
    assert "render_compact_header(" in source
    assert "if not is_study_demo_simple_ui()" in source

  def test_no_duplicate_title_in_simple_path(self) -> None:
    source = (ROOT / "ui_v9/signal_watch_app.py").read_text(encoding="utf-8")
    assert source.count('st.title("Tech Cartography v9")') == 1

  def test_demo_status_collapsed(self) -> None:
    source = (ROOT / "ui_v9/study_demo_compact_components.py").read_text(encoding="utf-8")
    assert 'expander("デモ環境について", expanded=False)' in source

  def test_analysis_duplicate_counts_zero(self) -> None:
    layout = analyze_simple_source_layout(mode="simple")
    assert layout["duplicate_header_count"] == 0
    assert layout["duplicate_context_count"] == 0
    assert layout["technical_id_visible_count"] == 0
    assert layout["legacy_tool_visible_count"] == 0


class TestThemeSimple:
  def test_theme_card_module_exists(self) -> None:
    source = (ROOT / "ui_v9/study_demo_simple_theme_ui.py").read_text(encoding="utf-8")
    assert "render_theme_summary_card" in source
    assert "検索条件を見る" in source
    assert "テーマを変更" in source

  def test_editor_only_on_button(self) -> None:
    source = (ROOT / "ui_v9/study_demo_simple_theme_ui.py").read_text(encoding="utf-8")
    assert "ui_simple_theme_edit_open" in source

  def test_selector_only_when_multiple_themes(self) -> None:
    source = (ROOT / "ui_v9/study_demo_simple_theme_ui.py").read_text(encoding="utf-8")
    assert "len(saved_themes) > 1" in source

  def test_selected_editor_theme_match_fixture(self) -> None:
    fx = _load_fixture()
    theme = dict(fx["themes"]["new_theme"])
    state = apply_editor_selection_metadata({}, theme)
    editor = theme_to_editor_values(theme)
    assert state["selected_saved_theme_id"] == "theme_6d2dfb753f7e"
    assert editor["name"] == theme["name"]


class TestSourcesSimple:
  def test_provider_cards_present(self) -> None:
    source = (ROOT / "ui_v9/study_demo_simple_sources_ui.py").read_text(encoding="utf-8")
    assert "render_provider_cards" in source
    assert "新しい検索を作成" in source
    assert "ui_simple_new_search_open" in source

  def test_legacy_hidden_in_simple_source(self) -> None:
    source = (ROOT / "ui_v9/study_demo_simple_sources_ui.py").read_text(encoding="utf-8")
    assert "should_show_legacy_tools()" in source


class TestSignalsSimple:
  def test_top3_deduplicated(self) -> None:
    signals = _signals_with_empty_title()
    top, remaining = split_top_and_remaining(signals)
    assert len(top) == 3
    top_keys = {f"{s.type}:{s.title}:{s.source_name}" for s in top}
    assert all(f"{s.type}:{s.title}:{s.source_name}" not in top_keys for s in remaining)

  def test_empty_title_hidden(self) -> None:
    visible, hidden = filter_signals_for_simple_display(_signals_with_empty_title())
    assert hidden == 1
    assert all(s.title for s in visible)

  def test_remaining_collapsed(self) -> None:
    source = (ROOT / "ui_v9/study_demo_simple_signals_ui.py").read_text(encoding="utf-8")
    assert "参考・低優先" in source
    assert "expanded=False" in source

  def test_no_related_companies_none_line(self) -> None:
    source = (ROOT / "ui_v9/study_demo_simple_signals_ui.py").read_text(encoding="utf-8")
    assert "関連企業" not in source


class TestWeeklyProfileDigestSimple:
  def test_weekly_baseline_text(self) -> None:
    source = (ROOT / "ui_v9/study_demo_simple_tabs_ui.py").read_text(encoding="utf-8")
    assert "初回ベースライン" in source

  def test_digest_download_limit(self) -> None:
    source = (ROOT / "ui_v9/study_demo_simple_tabs_ui.py").read_text(encoding="utf-8")
    assert source.count("st.download_button(") >= 2
    assert "実行証跡" in source


class TestSimpleUiCheck:
  def test_plan_status_ok(self) -> None:
    result = build_simple_ui_check_result(fixture=_load_fixture(), mode="simple")
    assert result["status"] == "ok"
    assert result["selected_theme_id"] == "theme_6d2dfb753f7e"
    assert result["active_run"] == "study_demo_search_20260705_145711_c06e0a1b"
    assert result["lineage_status"] == "connected"
    assert result["provider_counts"] == {"patent": 5, "paper": 5, "web": 5}
    assert result["integrated_count"] == 15
    assert result["tier_counts"] == {"A": 3, "B": 2, "C": 3, "D": 7}
    assert result["duplicate_signal_count"] == 0
    assert result["top_signal_count"] == 3
    assert result["remaining_signal_count"] == 12

  def test_signal_visibility_stats(self) -> None:
    stats = analyze_signal_visibility(signals=_signals_with_empty_title())
    assert stats["top_signal_count"] == 3
    assert stats["remaining_signal_count"] == 11
    assert stats["hidden_empty_title_count"] == 1


class TestRegressionSafety:
  def test_p0_lineage_ids_preserved(self) -> None:
    fx = _load_fixture()
    ctx = fx["active_context"]
    assert ctx["source_theme_id"] == "theme_6d2dfb753f7e"
    assert ctx["source_watch_profile_id"] == "wp_theme_6d2dfb753f7e"
    assert ctx["source_search_plan_id"] == "plan_wp_theme_6d2dfb753f7e"

  def test_advanced_mode_modules_preserved(self) -> None:
    assert (ROOT / "ui_v9/study_demo_sources_ui.py").is_file()
    assert (ROOT / "ui_v9/study_demo_saved_theme_editor_ui.py").is_file()

  @patch("ui_v9.study_demo_simple_signals_ui.st")
  @patch("ui_v9.study_demo_simple_signals_ui.build_research_value_bundle")
  def test_simple_signals_render_mock(self, mock_bundle: MagicMock, mock_st: MagicMock) -> None:
    from ui_v9.study_demo_simple_signals_ui import render_simple_signals_tab

    mock_bundle.return_value = {"items": []}
    mock_st.columns.side_effect = [
      [MagicMock(), MagicMock()],
      [MagicMock(), MagicMock(), MagicMock()],
      [MagicMock(), MagicMock(), MagicMock()],
    ]
    mock_st.multiselect.return_value = ["patent"]
    mock_st.markdown = MagicMock()
    mock_st.info = MagicMock()
    mock_st.caption = MagicMock()
    mock_st.expander.return_value.__enter__ = MagicMock(return_value=None)
    mock_st.expander.return_value.__exit__ = MagicMock(return_value=None)
    signals = _signals_with_empty_title()
    display = [s.to_dict() for s in signals if s.title]
    render_simple_signals_tab(
      signals=signals,
      display_signals=display,
      source_info={"active_context": {"active_search_run_id": "run-a"}},
    )
