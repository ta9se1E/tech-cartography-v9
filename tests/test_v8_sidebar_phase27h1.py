"""Tests for v8 sidebar labels (Phase 27H.1 / 27R.1 Judge Mode)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui.demo_safe_ui import sidebar_next_steps_text, sidebar_progress_text
from tech_cartography.ui.v8_tab_config import V8_STATUS_CAPTION, v8_sidebar_progress_text


def test_v8_status_caption_judge_mode() -> None:
  assert "Judge Mode" in V8_STATUS_CAPTION
  assert "UI骨格 Phase27B" not in V8_STATUS_CAPTION


def test_v8_sidebar_progress_includes_judge_flow() -> None:
  progress = v8_sidebar_progress_text()
  for token in (
    "Judge Overview",
    "Top5",
    "Claim Map",
    "Evidence Map",
    "未確認事項",
    "Weekly Watch",
    "共有レポート",
  ):
    assert token in progress


def test_v8_sidebar_helpers_via_demo_safe(monkeypatch) -> None:
  monkeypatch.setenv("APP_UI_VERSION", "v8")
  root = Path(__file__).resolve().parents[1]
  progress = sidebar_progress_text("analyst", project_root=root)
  next_steps = sidebar_next_steps_text("analyst", project_root=root)
  assert "Judge Overview" in progress or "Top5" in progress
  assert "35" in next_steps or "Top5全件" in next_steps
  assert "Final Validation" not in progress
  assert "Paper/Web" not in progress


def test_v8_sidebar_next_step_no_stale_single_claim_text() -> None:
  from tech_cartography.ui.v8_tab_config import v8_sidebar_next_steps_text

  text = v8_sidebar_next_steps_text()
  assert "1件手動投入" not in text
  assert "35" in text or "Top5全件" in text


def test_stale_phase27b_label_removed_from_intro() -> None:
  text = Path("src/tech_cartography/ui/v8_intro_ui.py").read_text(encoding="utf-8")
  assert "UI骨格 Phase27B" not in text
  assert "render_judge_conclusion_card" in text
  assert "1件手動投入" not in text
