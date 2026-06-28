"""Tests for Judge Mode UI copy and helpers (Phase 27R.1)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui.v8_judge_mode_copy import JUDGE_CONCLUSION_CARDS, JUDGE_NEXT_TAB
from tech_cartography.ui.v8_tab_config import V8_TAB_IDS, V8_TAB_LABELS, v8_tab_labels


def test_judge_mode_tab_labels_have_subtitles() -> None:
  labels = v8_tab_labels()
  assert len(labels) == len(V8_TAB_IDS)
  assert "Judge Overview" in labels[0]
  assert "Top5" in V8_TAB_LABELS["patent_shortlist"]
  assert "裏取り候補" in V8_TAB_LABELS["evidence_map"]
  assert "未確認事項" in V8_TAB_LABELS["gap_next_actions"]


def test_judge_conclusion_cards_cover_main_tabs() -> None:
  for tab_id in V8_TAB_IDS:
    assert tab_id in JUDGE_CONCLUSION_CARDS
    assert JUDGE_CONCLUSION_CARDS[tab_id].strip()


def test_judge_next_tab_map_has_demo_flow() -> None:
  assert JUDGE_NEXT_TAB["intro"] == "input"
  assert JUDGE_NEXT_TAB["patent_shortlist"] == "claim_map"
  assert JUDGE_NEXT_TAB["export"] == "intro"


def test_judge_mode_sidebar_module_exists() -> None:
  text = Path("src/tech_cartography/ui/v8_judge_mode_ui.py").read_text(encoding="utf-8")
  assert "render_judge_mode_sidebar" in text
  assert "load_case1_funnel_metrics" in text
