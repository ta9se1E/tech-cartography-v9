"""Tests for v8 text rendering helpers (Phase 27H.1)."""

from __future__ import annotations

from tech_cartography.ui.easy_japanese_ui import render_next_action_box
from tech_cartography.ui.v8_text_rendering import (
  normalize_text_items,
  render_bullet_items,
  render_next_action_card,
)


def test_normalize_text_items_single_string() -> None:
  text = "次は「入力」タブでテーマと案件を選んでください。"
  items = normalize_text_items(text)
  assert items == [text]
  assert len(items) == 1


def test_normalize_text_items_list() -> None:
  items = normalize_text_items(["A", "B"])
  assert items == ["A", "B"]


def test_normalize_text_items_none() -> None:
  assert normalize_text_items(None) == []


def test_str_not_split_char_by_char() -> None:
  text = "次は「入力」タブでテーマと案件を選んでください。"
  html = render_next_action_box(text)
  assert "<li>次は「入力」タブでテーマと案件を選んでください。</li>" in html
  assert html.count("<li>") == 1


def test_render_bullet_items_string() -> None:
  md = render_bullet_items("一行だけ")
  assert md == "- 一行だけ"


def test_render_next_action_card_list() -> None:
  html = render_next_action_card("次にやること", ["A", "B"])
  assert "<li>A</li>" in html
  assert "<li>B</li>" in html


def test_render_next_action_card_empty() -> None:
  html = render_next_action_card("次にやること", [])
  assert "次に行う操作はまだありません" in html
