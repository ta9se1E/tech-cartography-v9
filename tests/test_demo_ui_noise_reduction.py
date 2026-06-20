"""Tests for demo UI noise reduction (Phase 24.5F)."""

from __future__ import annotations

from pathlib import Path

V7_EASY_APP = Path("src/tech_cartography/ui/v7_easy_app.py")
EVIDENCE_DEMO = Path("src/tech_cartography/ui/evidence_map_demo.py")
DEMO_SAFE_UI = Path("src/tech_cartography/ui/demo_safe_ui.py")


def test_start_tab_single_usage_notices_expander() -> None:
  text = V7_EASY_APP.read_text(encoding="utf-8")
  start = text.split("def _tab_start", 1)[1].split("def _tab_patents", 1)[0]
  assert start.count("render_usage_notices_expander") == 1
  demo_block = start.split("if demo_mode and demo_artifacts is not None:", 1)[1].split(
    "if is_analyst_view():",
    1,
  )[0]
  assert "render_usage_notices_expander" not in demo_block


def test_demo_start_tab_usage_notices_at_bottom() -> None:
  text = EVIDENCE_DEMO.read_text(encoding="utf-8")
  fn = text.split("def render_demo_start_tab", 1)[1].split("def ", 1)[0]
  assert fn.count("render_usage_notices_expander(") == 1
  assert fn.index("render_three_minute_demo_guide") < fn.index("render_usage_notices_expander(")
  assert "expanded=False" in fn


def test_usage_notice_lines_not_duplicated_in_start_cards() -> None:
  text = EVIDENCE_DEMO.read_text(encoding="utf-8")
  story = text.split("def render_demo_story_cards", 1)[1].split("def render_evidence_map_summary", 1)[0]
  assert "FTO、侵害、有効性判断" not in story
  assert "supporting evidence candidate" not in story


def test_usage_notice_content_still_in_expander_source() -> None:
  text = DEMO_SAFE_UI.read_text(encoding="utf-8")
  assert "USAGE_NOTICE_LINES" in text
  assert "Paper候補は supporting evidence candidate" in text
  assert "FTO、侵害、有効性判断" in text
