"""Tests for SHOW_DEVELOPER_MODE visibility (Phase 24.5E)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui import demo_safe_ui
from tech_cartography.ui.developer_mode_visibility import SHOW_DEVELOPER_MODE_ENV

REPORT_TAB_UI = Path("src/tech_cartography/ui/report_tab_ui.py")
V7_EASY_APP = Path("src/tech_cartography/ui/v7_easy_app.py")


def test_is_developer_view_false_when_env_unset(monkeypatch) -> None:
  monkeypatch.delenv(SHOW_DEVELOPER_MODE_ENV, raising=False)

  class FakeSession:
    def get(self, key, default=None):
      return demo_safe_ui.UI_MODE_DEVELOPER

  import streamlit as st

  monkeypatch.setattr(st, "session_state", FakeSession(), raising=False)
  assert demo_safe_ui.is_developer_view() is False


def test_analyst_labels_remain_when_developer_hidden(monkeypatch) -> None:
  monkeypatch.delenv(SHOW_DEVELOPER_MODE_ENV, raising=False)
  labels = demo_safe_ui.tab_labels_for_ui_mode(demo_safe_ui.UI_MODE_ANALYST)
  assert "入力・実行" in labels
  assert "開発者向け" not in labels


def test_demo_labels_remain_when_developer_hidden(monkeypatch) -> None:
  monkeypatch.delenv(SHOW_DEVELOPER_MODE_ENV, raising=False)
  labels = demo_safe_ui.tab_labels_for_ui_mode(demo_safe_ui.UI_MODE_DEMO)
  assert labels == ["はじめる", "技術の裏取り", "企業・市場シグナル", "レポート", "設定"]


def test_developer_mode_label_in_sidebar_when_enabled(monkeypatch) -> None:
  monkeypatch.setenv(SHOW_DEVELOPER_MODE_ENV, "true")
  options = demo_safe_ui.visible_ui_mode_options()
  labels = [demo_safe_ui.UI_MODE_LABELS[m] for m in options]
  assert "開発者向け" in labels


def test_normalize_ui_mode_falls_back_from_developer(monkeypatch) -> None:
  monkeypatch.delenv(SHOW_DEVELOPER_MODE_ENV, raising=False)
  assert demo_safe_ui.normalize_ui_mode(demo_safe_ui.UI_MODE_DEVELOPER) == demo_safe_ui.UI_MODE_DEMO


def test_header_run_id_hidden_unless_developer_view() -> None:
  text = V7_EASY_APP.read_text(encoding="utf-8")
  section = text.split("def render_tabbed_easy_app", 1)[1].split("def render_easy_japanese_app", 1)[0]
  assert "if developer_mode:" in section
  assert "is_developer_view()" in text


def test_report_tab_caption_respects_developer_visibility_flag() -> None:
  text = REPORT_TAB_UI.read_text(encoding="utf-8")
  section = text.split("def render_compressed_report_tab", 1)[1].split(
    "def render_developer_report_expander",
    1,
  )[0]
  assert "is_show_developer_mode_enabled()" in section
