"""Tests for Cloud Run readiness UI checklist (Phase 24.5C)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui.report_tab_ui import build_cloud_run_checklist

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT_UI = Path("src/tech_cartography/ui/report_tab_ui.py")
APP_PY = Path("app.py")


def test_cloud_run_checklist_generated() -> None:
  checks = build_cloud_run_checklist(PROJECT_ROOT)
  assert len(checks) >= 8
  labels = {item["label"] for item in checks}
  assert "通常画面に /Users/ が出ていない" in labels
  assert "scheduler / launchd / cron は通常画面に出ていない" in labels
  assert "Review Packは生成済み" in labels


def test_cloud_run_checklist_has_passed_field() -> None:
  checks = build_cloud_run_checklist(PROJECT_ROOT)
  for item in checks:
    assert "passed" in item
    assert isinstance(item["passed"], bool)


def test_render_cloud_run_checklist_in_source() -> None:
  text = REPORT_UI.read_text(encoding="utf-8")
  assert "def render_cloud_run_ready_checklist" in text
  assert "Cloud Run 前チェックリスト" in text


def test_app_py_no_local_absolute_paths() -> None:
  assert "/Users/" not in APP_PY.read_text(encoding="utf-8")


def test_compressed_report_no_users_paths() -> None:
  compressed = REPORT_UI.read_text(encoding="utf-8").split("def render_compressed_report_tab", 1)[1].split(
    "def render_developer_report_expander",
    1,
  )[0]
  assert "/Users/" not in compressed


def test_settings_developer_has_checklist_expander() -> None:
  text = Path("src/tech_cartography/ui/user_settings_view.py").read_text(encoding="utf-8")
  assert "Cloud Run 前チェックリスト" in text
  assert "render_cloud_run_ready_checklist" in text
