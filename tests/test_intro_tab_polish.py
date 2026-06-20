"""Tests for intro tab polish (Phase 24.5B)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.ui.evidence_map_demo import (
  render_demo_start_tab,
  render_demo_story_cards,
  render_three_minute_demo_guide,
  render_ui_mode_guide_card,
  render_where_to_look_card,
)
from tech_cartography.ui.label_renderer import POLISHED_EVIDENCE_GAPS, POLISHED_NEXT_ACTIONS
from tech_cartography.ui.evidence_map_demo import get_fixed_evidence_gaps, get_fixed_next_actions

DEMO_UI = Path("src/tech_cartography/ui/evidence_map_demo.py")


def test_where_to_look_card_content() -> None:
  html = render_where_to_look_card()
  assert "どこを見れば何が分かるか" in html
  assert "技術の裏取り" in html
  assert "企業・市場シグナル" in html
  assert "レポート" in html
  assert "本番実行" in html


def test_ui_mode_guide_card() -> None:
  html = render_ui_mode_guide_card(include_developer_mode=True)
  assert "デモを見る" in html
  assert "本番実行" in html
  assert "開発者向け" in html
  hidden = render_ui_mode_guide_card(include_developer_mode=False)
  assert "開発者向け" not in hidden


def test_deep_dive_replaced_in_story_cards() -> None:
  html = render_demo_story_cards()
  assert "今回詳しく読む特許" in html
  assert "Deep Dive" not in html
  assert DEMO_UI.read_text(encoding="utf-8").count("Deep Dive") <= 1


def test_story_cards_no_run_id_or_bigquery_in_main_cards() -> None:
  html = render_demo_story_cards()
  assert "run_id" not in html
  assert "BigQuery" not in html


def test_demo_start_uses_usage_notices_expander() -> None:
  text = DEMO_UI.read_text(encoding="utf-8")
  start = text.split("def render_demo_start_tab", 1)[1].split("def ", 1)[0]
  assert "render_usage_notices_expander" in start
  assert "demo_us_12565719_b2" not in start


def test_polished_evidence_gaps_and_actions() -> None:
  gaps = get_fixed_evidence_gaps()
  actions = get_fixed_next_actions()
  assert gaps == list(POLISHED_EVIDENCE_GAPS)
  assert actions == list(POLISHED_NEXT_ACTIONS)
  assert "明細書・実施例が未確認" in gaps
  assert "Google Patents / J-PlatPat" in actions[0]
  assert "上位3件" in actions[2]


def test_three_minute_guide_mentions_evidence_and_signals() -> None:
  guide = render_three_minute_demo_guide()
  assert "3分デモの見方" in guide
  assert "企業・市場シグナル" in guide
