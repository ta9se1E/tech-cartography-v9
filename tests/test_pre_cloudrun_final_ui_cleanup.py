"""Tests for pre-Cloud Run final UI cleanup (Phase 24.5E)."""

from __future__ import annotations

import os
from pathlib import Path

from tech_cartography.ui import demo_safe_ui, v7_easy_app
from tech_cartography.ui.developer_mode_visibility import (
  SHOW_DEVELOPER_MODE_ENV,
  is_show_developer_mode_enabled,
)
from tech_cartography.ui.evidence_map_demo import render_ui_mode_guide_card

V7_EASY_APP = Path("src/tech_cartography/ui/v7_easy_app.py")
DEMO_SAFE_UI = Path("src/tech_cartography/ui/demo_safe_ui.py")
USER_SETTINGS = Path("src/tech_cartography/ui/user_settings_view.py")
REPRO_UI = Path("src/tech_cartography/ui/reproducibility_smoke_ui.py")


def test_show_developer_mode_defaults_false(monkeypatch) -> None:
  monkeypatch.delenv(SHOW_DEVELOPER_MODE_ENV, raising=False)
  assert is_show_developer_mode_enabled() is False


def test_show_developer_mode_false_values(monkeypatch) -> None:
  for value in ("false", "0", "no", ""):
    monkeypatch.setenv(SHOW_DEVELOPER_MODE_ENV, value)
    assert is_show_developer_mode_enabled() is False


def test_show_developer_mode_true_values(monkeypatch) -> None:
  for value in ("true", "1", "yes", "on", "TRUE"):
    monkeypatch.setenv(SHOW_DEVELOPER_MODE_ENV, value)
    assert is_show_developer_mode_enabled() is True


def test_visible_ui_mode_options_respect_env(monkeypatch) -> None:
  monkeypatch.delenv(SHOW_DEVELOPER_MODE_ENV, raising=False)
  hidden = demo_safe_ui.visible_ui_mode_options()
  assert hidden == (demo_safe_ui.UI_MODE_DEMO, demo_safe_ui.UI_MODE_ANALYST)
  assert demo_safe_ui.UI_MODE_DEVELOPER not in hidden

  monkeypatch.setenv(SHOW_DEVELOPER_MODE_ENV, "true")
  shown = demo_safe_ui.visible_ui_mode_options()
  assert demo_safe_ui.UI_MODE_DEVELOPER in shown


def test_demo_evidence_tab_does_not_render_reproducibility_brief() -> None:
  text = V7_EASY_APP.read_text(encoding="utf-8")
  evidence = text.split("def _tab_evidence", 1)[1].split("def _tab_market", 1)[0]
  demo_block = evidence.split("if demo_artifacts is not None:", 1)[1].split("if is_analyst_view():", 1)[0]
  assert "render_reproducibility_brief_section" not in demo_block
  assert "render_demo_evidence_tab" in demo_block


def test_demo_start_tab_does_not_render_reproducibility_brief() -> None:
  text = V7_EASY_APP.read_text(encoding="utf-8")
  start = text.split("def _tab_start", 1)[1].split("def _tab_patents", 1)[0]
  demo_block = start.split("if demo_mode and demo_artifacts is not None:", 1)[1].split("if is_analyst_view():", 1)[0]
  assert "render_reproducibility_brief_section" not in demo_block


def test_reproducibility_brief_only_in_developer_reports_path() -> None:
  text = V7_EASY_APP.read_text(encoding="utf-8")
  assert "load_reproducibility_smoke_artifacts(PROJECT_ROOT)" in text
  assert "if demo_mode and developer_mode" in text
  reports = text.split("def _tab_reports", 1)[1].split("def _main_tab_labels", 1)[0]
  assert "render_reproducibility_smoke_section" in reports


def test_demo_ui_mode_guide_hides_developer_by_default() -> None:
  html = render_ui_mode_guide_card(include_developer_mode=False)
  assert "デモを見る" in html
  assert "本番実行" in html
  assert "開発者向け" not in html


def test_settings_tab_shows_hidden_notice_when_developer_disabled() -> None:
  text = USER_SETTINGS.read_text(encoding="utf-8")
  assert "developer_mode_hidden_notice" in text
  assert "is_show_developer_mode_enabled()" in text


def test_sidebar_uses_visible_ui_mode_options() -> None:
  section = DEMO_SAFE_UI.read_text(encoding="utf-8").split("def render_app_sidebar", 1)[1].split(
    "\ndef ",
    1,
  )[0]
  assert "visible_ui_mode_options" in section
  assert "list(visible_options)" in section


def test_reproducibility_card_text_isolated_to_module() -> None:
  text = REPRO_UI.read_text(encoding="utf-8")
  assert "再現性確認の現在地" in text
  assert "Manual Claims Route required" in text
  assert "render_reproducibility_brief_section" in text


def test_demo_evidence_tab_keeps_core_sections() -> None:
  text = Path("src/tech_cartography/ui/evidence_map_demo.py").read_text(encoding="utf-8")
  evidence_fn = text.split("def render_demo_evidence_tab", 1)[1].split("def render_demo_start_tab", 1)[0]
  assert "render_evidence_map_summary" in evidence_fn
  assert "render_selected_evidence_papers" in evidence_fn
  assert "render_evidence_gaps_and_next_actions" in evidence_fn
  assert "render_reproducibility_brief_section" not in evidence_fn
