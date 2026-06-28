"""UI tests for v8 large candidate ranking (Phase 27J.1)."""

from __future__ import annotations

from pathlib import Path


def test_patent_shortlist_ui_ranking_fields() -> None:
  shortlist = Path("src/tech_cartography/ui/v8_patent_shortlist_ui.py").read_text(encoding="utf-8")
  top5_ui = Path("src/tech_cartography/ui/v8_top5_reading_ui.py").read_text(encoding="utf-8")
  combined = shortlist + top5_ui
  for token in (
    "Ranking Policy",
    "why_selected",
    "positive_reasons",
    "negative_reasons",
    "スコアリング方針",
    "Top20から落ちた候補",
    "Top5のみ",
  ):
    assert token in combined
  assert "Generate Reading Priority" in shortlist
  assert "use_container_width" not in shortlist


def test_export_ui_ranking_explanation_pack() -> None:
  text = Path("src/tech_cartography/ui/v8_export_ui.py").read_text(encoding="utf-8")
  assert "Ranking Explanation Pack" in text
  assert "ranking_explanation.md" in text
  assert "triage_engine" in text
  assert "use_container_width" not in text


def test_sources_ui_large_candidate_guidance() -> None:
  text = Path("src/tech_cartography/ui/v8_sources_ui.py").read_text(encoding="utf-8")
  assert "段階選抜" in text or "Ranking Explanation" in text
  assert "dedupe report" in text
