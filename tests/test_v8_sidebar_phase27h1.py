"""Tests for v8 sidebar labels (Phase 27H.1)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui.demo_safe_ui import sidebar_next_steps_text, sidebar_progress_text
from tech_cartography.ui.v8_tab_config import V8_STATUS_CAPTION, v8_sidebar_progress_text


def test_v8_status_caption_mentions_current_phase() -> None:
  assert "Phase27J" in V8_STATUS_CAPTION or "Phase27I" in V8_STATUS_CAPTION or "Phase27K" in V8_STATUS_CAPTION
  assert (
    "1000" in V8_STATUS_CAPTION
    or "Ranking" in V8_STATUS_CAPTION
    or "Manual Claim" in V8_STATUS_CAPTION
    or "3案件" in V8_STATUS_CAPTION
  )
  assert "UI骨格 Phase27B" not in V8_STATUS_CAPTION


def test_v8_sidebar_progress_includes_v8_flow() -> None:
  progress = v8_sidebar_progress_text()
  for token in (
    "Sources一覧",
    "読むべき特許",
    "Claim Map",
    "Evidence Map",
    "Gap / Next Actions",
    "定点観測",
    "Export",
  ):
    assert token in progress


def test_v8_sidebar_helpers_via_demo_safe(monkeypatch) -> None:
  monkeypatch.setenv("APP_UI_VERSION", "v8")
  root = Path(__file__).resolve().parents[1]
  progress = sidebar_progress_text("analyst", project_root=root)
  next_steps = sidebar_next_steps_text("analyst", project_root=root)
  assert "Sources一覧" in progress
  assert "3案件検証パック" in next_steps or "claim" in next_steps.lower() or "1000" in next_steps or "Top100" in next_steps or "Ranking" in next_steps or "Manual Claim" in next_steps
  assert "Final Validation" not in progress
  assert "Paper/Web" not in progress


def test_stale_phase27b_label_removed_from_intro() -> None:
  text = Path("src/tech_cartography/ui/v8_intro_ui.py").read_text(encoding="utf-8")
  assert "UI骨格 Phase27B" not in text
  assert "V8_STATUS_CAPTION" in text
