"""Tests for report status Japanese labels (Phase 24.5F)."""

from __future__ import annotations

from tech_cartography.ui import report_tab_ui
from tech_cartography.ui.label_renderer import translate_report_status


def test_translate_freeze_readiness() -> None:
  assert translate_report_status("freeze_ready_after_cross_theme_end_to_end_validation") == "MVPデモ可能"


def test_translate_evidence_level() -> None:
  assert translate_report_status("cross_theme_end_to_end_with_actual_paper_web_data") == (
    "別テーマでもPaper/Web実データまで確認済み"
  )
  assert translate_report_status("actual_data") == "実データ取得済み"
  assert translate_report_status("query_plan_ready") == "検索計画作成済み"


def test_brief_lines_hide_internal_tokens() -> None:
  lines = report_tab_ui.build_final_validation_brief_lines(
    {
      "seed_count": 3,
      "completed_end_to_end_count": 3,
      "freeze_readiness": "freeze_ready_after_cross_theme_end_to_end_validation",
      "evidence_level": "cross_theme_end_to_end_with_actual_paper_web_data",
    },
  )
  joined = "\n".join(lines)
  assert "freeze_ready_after_cross_theme" not in joined
  assert "actual_data" not in joined
  assert "completed_end_to_end_count" not in joined
  assert "MVPデモ可能" in joined
  assert "実データ" in joined or "Paper/Web" in joined


def test_brief_lines_show_japanese_seed_summary() -> None:
  lines = report_tab_ui.build_final_validation_brief_lines(
    {"seed_count": 3, "completed_end_to_end_count": 3, "freeze_readiness": "", "evidence_level": ""},
  )
  assert any("JP seed 3件" in line for line in lines)
