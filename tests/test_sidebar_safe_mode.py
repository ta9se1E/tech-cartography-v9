"""Tests for demo-safe sidebar (Phase 24.5A)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui import demo_safe_ui

SIDEBAR_MODULE = Path("src/tech_cartography/ui/demo_safe_ui.py")
APP_PY = Path("app.py")
V7_EASY_APP = Path("src/tech_cartography/ui/v7_easy_app.py")


def _sidebar_fn_text() -> str:
  text = SIDEBAR_MODULE.read_text(encoding="utf-8")
  return text.split("def render_app_sidebar", 1)[1].split("\ndef ", 1)[0]


def test_sidebar_has_three_ui_modes() -> None:
  text = SIDEBAR_MODULE.read_text(encoding="utf-8")
  section = _sidebar_fn_text()
  assert "UI_MODE_DEMO" in section
  assert "UI_MODE_ANALYST" in section
  assert "UI_MODE_DEVELOPER" in section
  assert "UI_MODE_LABELS" in text
  assert demo_safe_ui.UI_MODE_LABELS[demo_safe_ui.UI_MODE_DEMO] == "デモを見る"


def test_sidebar_shows_progress_and_next_steps() -> None:
  section = _sidebar_fn_text()
  assert "sidebar_progress_text" in section
  assert "sidebar_next_steps_text" in section
  assert "現在の進捗" in section
  assert "次にやること" in section


def test_run_id_not_in_normal_sidebar() -> None:
  section = _sidebar_fn_text()
  normal_part = section.split("if ui_mode_input == UI_MODE_DEVELOPER and is_show_developer_mode_enabled():", 1)[0]
  assert "run_id" not in normal_part
  assert "latest_run を読み込む" not in normal_part
  assert "デモ成果物を読み込む" not in normal_part
  assert "実行結果フォルダ" not in normal_part


def test_developer_expander_contains_run_id_and_paths() -> None:
  text = SIDEBAR_MODULE.read_text(encoding="utf-8")
  expander = text.split("def render_developer_info_expander", 1)[1].split("def render_app_sidebar", 1)[0]
  assert "開発者向け情報" in expander
  assert "run_id:" in expander
  assert "outputs path:" in expander
  assert "format_display_path" in expander
  assert "/Users/" not in expander


def test_format_display_path_uses_relative_outputs() -> None:
  root = Path("/Users/example/project")
  rel = demo_safe_ui.format_display_path(
    root / "outputs" / "pipeline_runs" / "run-1",
    project_root=root,
  )
  assert rel == "outputs/pipeline_runs/run-1"
  assert "/Users/" not in rel


def test_app_py_sidebar_does_not_expose_local_paths() -> None:
  text = APP_PY.read_text(encoding="utf-8")
  assert "/Users/" not in text
  assert "selected_run_id_input" not in text


def test_scheduler_notice_post_mvp_in_developer_expander() -> None:
  text = SIDEBAR_MODULE.read_text(encoding="utf-8")
  assert "SCHEDULER_POST_MVP_NOTICE" in text
  assert "Post-MVP" in text
  assert "launchd" in text


def test_delivery_ui_hides_scheduler_from_normal_mode() -> None:
  text = Path("src/tech_cartography/ui/delivery_ui.py").read_text(encoding="utf-8")
  section = text.split("def render_delivery_section", 1)[1].split("\ndef ", 1)[0]
  assert "render_send_log_section" in section
  assert "render_weekly_schedule_section" in section
  pre_dev = section.split("if developer_mode:", 1)[0]
  assert "render_send_log_section" not in pre_dev
  assert "render_weekly_schedule_section" not in pre_dev


def test_v7_header_hides_run_id_for_demo_and_analyst() -> None:
  text = V7_EASY_APP.read_text(encoding="utf-8")
  render_section = text.split("def render_tabbed_easy_app", 1)[1].split("def render_easy_japanese_app", 1)[0]
  assert "if developer_mode:" in render_section
  assert "run_id:" in render_section
