"""Tests for compressed report tab (Phase 24.5C)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui import report_tab_ui, v7_easy_app

REPORT_UI = Path("src/tech_cartography/ui/report_tab_ui.py")
V7_EASY_APP = Path("src/tech_cartography/ui/v7_easy_app.py")


def test_compressed_report_tab_function_exists() -> None:
  text = V7_EASY_APP.read_text(encoding="utf-8")
  assert "render_compressed_report_tab" in text
  reports_fn = text.split("def _tab_reports", 1)[1].split("\ndef _main_tab_labels", 1)[0]
  assert "render_delivery_section" not in reports_fn
  assert "render_developer_report_expander" in reports_fn


def test_normal_report_shows_executive_summary_and_exports() -> None:
  text = REPORT_UI.read_text(encoding="utf-8")
  compressed = text.split("def render_compressed_report_tab", 1)[1].split("def render_developer_report_expander", 1)[0]
  assert "Executive Summary" in compressed
  assert "Evidence Map" in compressed
  assert "_render_digest_preview_highlights" in compressed
  assert "_render_export_buttons" in compressed
  assert "render_final_validation_brief_section" in compressed


def test_normal_report_hides_validation_and_scheduler() -> None:
  compressed = REPORT_UI.read_text(encoding="utf-8").split("def render_compressed_report_tab", 1)[1].split(
    "def render_developer_report_expander",
    1,
  )[0]
  assert "reviewer_response" not in compressed
  assert "render_send_log_section" not in compressed
  assert "render_weekly_schedule_section" not in compressed
  assert "core_validation_summary" not in compressed.lower()
  assert "scheduler_readme" not in compressed


def test_developer_expander_contains_hidden_sections() -> None:
  dev = REPORT_UI.read_text(encoding="utf-8").split("def render_developer_report_expander", 1)[1]
  assert "render_send_log_section" in dev
  assert "render_weekly_schedule_section" in dev
  assert "render_email_draft_preview_section" in dev
  assert "render_cloud_run_ready_checklist" in dev
  assert 'expander("開発者向け情報 / 詳細レポート"' in dev


def test_final_validation_brief_lines() -> None:
  lines = report_tab_ui.build_final_validation_brief_lines(
    {
      "seed_count": 3,
      "completed_end_to_end_count": 3,
      "freeze_readiness": "freeze_ready_after_cross_theme_end_to_end_validation",
      "evidence_level": "cross_theme_end_to_end_with_actual_paper_web_data",
    },
  )
  assert any("JP seed 3件" in line for line in lines)
  assert any("MVPデモ可能" in line for line in lines)
  assert any("確認候補" in line for line in lines)
  joined = "\n".join(lines)
  assert "actual_data" not in joined
  assert "freeze_ready_after" not in joined


def test_validation_links_only_in_developer_mode() -> None:
  text = V7_EASY_APP.read_text(encoding="utf-8")
  assert "if not developer_mode:" in text.split("def _tab_reports_core_validation_summary_links", 1)[1][:200]
  assert "if not developer_mode:" in text.split("def _tab_reports_final_validation_summary_links", 1)[1][:200]
