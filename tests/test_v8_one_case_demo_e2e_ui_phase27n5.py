"""Tests for Phase27N.5 One Case Demo E2E UI."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"


def _read(rel: str) -> str:
  return (SRC / rel).read_text(encoding="utf-8")


def test_export_ui_one_case_e2e() -> None:
  text = _read("tech_cartography/ui/v8_export_ui.py")
  assert "One Case Real Demo E2E" in text
  assert "case_01_bigquery_export_1000" in text or "DEFAULT_ONE_CASE_INPUT_CSV" in text
  assert "use_container_width" not in text


def test_intro_case1_real_demo() -> None:
  text = _read("tech_cartography/ui/v8_intro_ui.py")
  assert "Phase27N.5" in text or "render_judge_conclusion_card" in text or "35請求項" in text or "INTRO_FUNNEL_SUMMARY" in text
  assert "Case 1" in text or "case_01" in text or "INTRO_FUNNEL_SUMMARY" in text
  assert "claim 本文" in text or "claim" in text or "35" in text or "請求項" in text
  assert "render_next_action_card" in text or "render_judge_three_minute_guide" in text
  assert "use_container_width" not in text


def test_tab_config_phase27n5() -> None:
  text = _read("tech_cartography/ui/v8_tab_config.py")
  assert (
    "Phase27N.5" in text
    or "Phase27Q.1" in text
    or "Phase27Q.3" in text
    or "Judge Mode" in text
  )
  assert "UI骨格 Phase27B" not in text


def test_sidebar_phase27n5() -> None:
  text = _read("tech_cartography/ui/demo_safe_ui.py")
  assert (
    "Phase27N.5" in text
    or "Phase27Q.3" in text
    or "Submission Demo" in text
    or "render_judge_mode_sidebar" in text
    or "Judge Mode" in text
  )
  assert "use_container_width" not in text
