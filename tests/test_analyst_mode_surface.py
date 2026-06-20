"""Tests for analyst mode surface polish (Phase 24.5D)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui import demo_safe_ui, theme_validation_ui, v7_easy_app
from tech_cartography.ui.analyst_mode_ui import (
  ANALYST_EMPTY_ARTIFACT_MESSAGE,
  ANALYST_INPUT_KEY_PREFIX,
  PAN_PRECURSOR_THEME_PRESET,
  pan_theme_session_state_updates,
)
from tech_cartography.ui.japanese_labels import TAB_LABELS, translate_tab_name

PROJECT_ROOT = Path(__file__).resolve().parent.parent
V7_EASY_APP = PROJECT_ROOT / "src" / "tech_cartography" / "ui" / "v7_easy_app.py"
THEME_VALIDATION_UI = PROJECT_ROOT / "src" / "tech_cartography" / "ui" / "theme_validation_ui.py"
DEMO_SAFE_UI = PROJECT_ROOT / "src" / "tech_cartography" / "ui" / "demo_safe_ui.py"


def test_analyst_mode_shows_input_execution_tab() -> None:
  analyst_ids = demo_safe_ui.tab_ids_for_ui_mode(demo_safe_ui.UI_MODE_ANALYST)
  assert analyst_ids[0] == "analyst_input"
  labels = demo_safe_ui.tab_labels_for_ui_mode(demo_safe_ui.UI_MODE_ANALYST)
  assert labels[0] == "入力・実行"
  assert "別テーマ検証" not in labels
  assert "本番実行" not in labels[1:]


def test_demo_mode_hides_input_execution_tab() -> None:
  demo_ids = demo_safe_ui.tab_ids_for_ui_mode(demo_safe_ui.UI_MODE_DEMO)
  assert "analyst_input" not in demo_ids
  demo_labels = demo_safe_ui.tab_labels_for_ui_mode(demo_safe_ui.UI_MODE_DEMO)
  assert "入力・実行" not in demo_labels


def test_analyst_input_tab_has_step_cards_and_expanders() -> None:
  ui_text = THEME_VALIDATION_UI.read_text(encoding="utf-8")
  analyst_text = Path("src/tech_cartography/ui/analyst_mode_ui.py").read_text(encoding="utf-8")
  assert "def render_analyst_input_execution_section" in ui_text
  assert "Step 1: テーマを入力する" in analyst_text
  assert "Step 7: 結果を見る" in analyst_text
  assert 'expander("1. テーマ・seed入力"' in ui_text
  assert 'expander("5. Final Validation"' in ui_text


def test_analyst_start_tab_has_production_guidance() -> None:
  text = V7_EASY_APP.read_text(encoding="utf-8")
  start_section = text.split("def _tab_start", 1)[1].split("def _tab_patents", 1)[0]
  assert "入力・実行" in start_section
  assert "成果物が生成された後は" in start_section


def test_analyst_result_tabs_show_empty_message() -> None:
  text = V7_EASY_APP.read_text(encoding="utf-8")
  assert "ANALYST_EMPTY_ARTIFACT_MESSAGE" in text
  evidence_section = text.split("def _tab_evidence", 1)[1].split("def _tab_market", 1)[0]
  reports_section = text.split("def _tab_reports", 1)[1].split("def _main_tab_labels", 1)[0]
  assert "is_analyst_view()" in evidence_section
  assert "ANALYST_EMPTY_ARTIFACT_MESSAGE" in evidence_section
  assert "ANALYST_EMPTY_ARTIFACT_MESSAGE" in reports_section
  assert ANALYST_EMPTY_ARTIFACT_MESSAGE.endswith("実行してください")


def test_analyst_mode_avoids_absolute_paths_in_ui() -> None:
  text = THEME_VALIDATION_UI.read_text(encoding="utf-8")
  assert "def _show_output_path" in text
  assert "format_display_path" in text
  assert "/Users/" not in text


def test_analyst_mode_does_not_duplicate_long_warnings() -> None:
  text = THEME_VALIDATION_UI.read_text(encoding="utf-8")
  safety = text.split("def render_theme_validation_safety_messages", 1)[1].split("def _build_case_from_inputs", 1)[0]
  assert "THEME_VALIDATION_SAFETY_MESSAGES" not in safety
  assert "for notice in THEME_VALIDATION_SAFETY_MESSAGES" not in text
  assert "for notice in END_TO_END_UI_NOTICES" in text


def test_no_mail_or_scheduler_buttons_in_analyst_surface() -> None:
  for path in (V7_EASY_APP, THEME_VALIDATION_UI):
    text = path.read_text(encoding="utf-8").lower()
    assert "send_email" not in text
    assert "schedule_weekly" not in text
    assert "launchd" not in text or "post-mvp" in text.lower()


def test_translate_tab_name_for_analyst_input() -> None:
  assert translate_tab_name("analyst_input") == "入力・実行"
  assert TAB_LABELS["analyst_input"] == "入力・実行"


def test_v7_easy_app_wires_analyst_input_tab() -> None:
  text = V7_EASY_APP.read_text(encoding="utf-8")
  assert "def _tab_analyst_input" in text
  assert 'tab_id == "analyst_input"' in text
  assert "render_analyst_input_execution_section" in text
