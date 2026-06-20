"""Tests for demo-safe UI modes (Phase 24.5A)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui import demo_safe_ui, v7_easy_app

PROJECT_ROOT = Path(__file__).resolve().parent.parent
V7_EASY_APP = PROJECT_ROOT / "src" / "tech_cartography" / "ui" / "v7_easy_app.py"
DEMO_SAFE_UI = PROJECT_ROOT / "src" / "tech_cartography" / "ui" / "demo_safe_ui.py"
THEME_VALIDATION_UI = PROJECT_ROOT / "src" / "tech_cartography" / "ui" / "theme_validation_ui.py"
APP_PY = PROJECT_ROOT / "app.py"


def test_demo_tab_ids_exclude_analyst_inputs() -> None:
  demo_ids = demo_safe_ui.tab_ids_for_ui_mode(demo_safe_ui.UI_MODE_DEMO)
  assert "theme_validation" not in demo_ids
  assert "patents" not in demo_ids
  assert "fulltext" not in demo_ids
  assert demo_ids == demo_safe_ui.DEMO_TAB_IDS


def test_analyst_tab_ids_include_input_execution() -> None:
  analyst_ids = demo_safe_ui.tab_ids_for_ui_mode(demo_safe_ui.UI_MODE_ANALYST)
  assert "analyst_input" in analyst_ids
  assert "theme_validation" not in analyst_ids
  labels = demo_safe_ui.tab_labels_for_ui_mode(demo_safe_ui.UI_MODE_ANALYST)
  assert "入力・実行" in labels
  assert "別テーマ検証" not in labels


def test_demo_mode_default_in_session_state() -> None:
  from tech_cartography.ui.streamlit_session import STATE_UI_MODE, default_app_session_state

  state = default_app_session_state(None)
  assert state[STATE_UI_MODE] == demo_safe_ui.UI_MODE_DEMO


def test_usage_notices_centralized() -> None:
  text = V7_EASY_APP.read_text(encoding="utf-8")
  assert "render_usage_notices_expander" in text
  assert "USAGE_NOTICE_LINES" in DEMO_SAFE_UI.read_text(encoding="utf-8")
  start_section = text.split("def _tab_start", 1)[1].split("def _tab_patents", 1)[0]
  assert "BigQuery/OpenAlex" not in start_section


def test_demo_mode_does_not_render_theme_validation_tab() -> None:
  text = V7_EASY_APP.read_text(encoding="utf-8")
  assert "tab_ids_for_ui_mode" in text
  assert "DEMO_TAB_IDS" in DEMO_SAFE_UI.read_text(encoding="utf-8")
  render_section = text.split("def render_tabbed_easy_app", 1)[1].split("def render_easy_japanese_app", 1)[0]
  assert "with tabs[5]:" not in render_section
  assert "_render_tab_by_id" in render_section


def test_run_id_hidden_from_header_unless_developer() -> None:
  text = V7_EASY_APP.read_text(encoding="utf-8")
  header_section = text.split("header_cols = st.columns", 1)[1].split("root = pipeline_root", 1)[0]
  assert "if developer_mode:" in header_section
  assert header_section.index("if developer_mode:") < header_section.index("run_id:")


def test_validation_summaries_developer_only() -> None:
  text = V7_EASY_APP.read_text(encoding="utf-8")
  assert "developer_mode: bool = False" in text
  core_fn = text.split("def _tab_reports_core_validation_summary_links", 1)[1].split(
    "def _tab_reports_final_validation_summary_links",
    1,
  )[0]
  assert "if not developer_mode:" in core_fn


def test_delivery_section_developer_mode_flag() -> None:
  text = Path("src/tech_cartography/ui/delivery_ui.py").read_text(encoding="utf-8")
  section = text.split("def render_delivery_section", 1)[1].split("def ", 2)[0]
  assert "developer_mode: bool = False" in section
  assert "if developer_mode:" in section
  assert "render_weekly_schedule_section" in section
  assert section.index("if developer_mode:") < section.index("render_weekly_schedule_section")


def test_theme_validation_renamed_to_production_run() -> None:
  text = THEME_VALIDATION_UI.read_text(encoding="utf-8")
  assert 'st.subheader("本番実行 / 新しいテーマで分析")' in text
  safety = text.split("def render_theme_validation_safety_messages", 1)[1].split("def _build_case_from_inputs", 1)[0]
  assert "THEME_VALIDATION_SAFETY_MESSAGES" not in safety
  assert "利用上の注意" in safety


def test_external_api_consent_remains_in_theme_validation() -> None:
  text = THEME_VALIDATION_UI.read_text(encoding="utf-8")
  assert "外部検索の同意チェックが必要です" in text
  assert "allow_external_api" in text


def test_app_py_uses_demo_safe_sidebar() -> None:
  text = APP_PY.read_text(encoding="utf-8")
  assert "render_app_sidebar" in text
  assert "WIDGET_PIPELINE_ROOT" not in text
  assert "/Users/" not in text
