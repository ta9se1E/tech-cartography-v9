"""UI routing tests for theme validation tab (Phase 24.4A.1)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui import theme_validation_ui, v7_easy_app
from tech_cartography.ui.japanese_labels import TAB_LABELS, translate_tab_name

PROJECT_ROOT = Path(__file__).resolve().parent.parent
V7_EASY_APP = PROJECT_ROOT / "src" / "tech_cartography" / "ui" / "v7_easy_app.py"
THEME_VALIDATION_UI = PROJECT_ROOT / "src" / "tech_cartography" / "ui" / "theme_validation_ui.py"
APP_PY = PROJECT_ROOT / "app.py"


def test_app_py_uses_render_tabbed_easy_app() -> None:
  text = APP_PY.read_text(encoding="utf-8")
  assert "from tech_cartography.ui.v7_easy_app import" in text
  assert "render_tabbed_easy_app" in text


def test_main_tab_labels_use_demo_safe_ui() -> None:
  demo_labels = v7_easy_app._main_tab_labels(ui_mode="demo")
  assert "本番実行" not in demo_labels
  assert "別テーマ検証" not in demo_labels
  assert "入力・実行" not in demo_labels
  assert "はじめる" in demo_labels
  analyst_labels = v7_easy_app._main_tab_labels(ui_mode="analyst")
  assert "入力・実行" in analyst_labels
  assert "別テーマ検証" not in analyst_labels
  assert translate_tab_name("theme_validation") == "別テーマ検証"
  assert TAB_LABELS["theme_validation"] == "別テーマ検証"


def test_v7_easy_app_wires_theme_validation_tab() -> None:
  text = V7_EASY_APP.read_text(encoding="utf-8")
  assert "def _tab_analyst_input" in text
  assert "render_analyst_input_execution_section" in text
  assert "render_theme_validation_section" in text
  assert "tab_ids_for_ui_mode" in text
  assert "_render_tab_by_id" in text
  assert "tabs = st.tabs(_main_tab_labels())" not in text


def test_reports_tab_points_to_theme_validation_tab() -> None:
  text = V7_EASY_APP.read_text(encoding="utf-8")
  assert "_tab_reports_theme_validation_links" in text
  assert "developer_mode" in text.split("def _tab_reports_theme_validation_links", 1)[1].split("def _tab_reports", 1)[0]
  assert "render_theme_validation_section(key_prefix=\"reports_theme_validation\")" not in text


def test_theme_validation_ui_has_input_labels() -> None:
  text = THEME_VALIDATION_UI.read_text(encoding="utf-8")
  for label in (
    "テーマ名",
    "テーマ説明",
    "コアキーワード",
    "用途キーワード",
    "材料・プロセスキーワード",
    "除外キーワード",
    "seed publication numbers",
  ):
    assert label in text


def test_theme_validation_ui_has_action_buttons() -> None:
  text = THEME_VALIDATION_UI.read_text(encoding="utf-8")
  assert "検索計画を作成する（dry-run）" in text
  assert "既存outputsだけで検証する" in text
  assert "Manual Claimsテンプレートを作成する" in text


def test_theme_validation_ui_has_tab_intro_copy() -> None:
  text = THEME_VALIDATION_UI.read_text(encoding="utf-8")
  assert "新しいテーマで Tech Cartography の流れ" in text
  assert "dry-run" in text


def test_theme_validation_ui_has_no_mail_or_scheduler_buttons() -> None:
  text = THEME_VALIDATION_UI.read_text(encoding="utf-8").lower()
  forbidden = (
    "launchd",
    "smtp",
    "send_email",
    "install_weekly",
  )
  for token in forbidden:
    assert token not in text
  assert "render_live_scheduler_dry_run_section" in text


def test_render_theme_validation_section_is_callable_from_tab_helper() -> None:
  assert callable(theme_validation_ui.render_theme_validation_section)
  assert callable(v7_easy_app._tab_theme_validation)
