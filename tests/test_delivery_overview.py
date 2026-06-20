"""Tests for delivery overview (Phase 24.0)."""

from __future__ import annotations

from tech_cartography.delivery.overview import build_tab_overviews, render_overview_page_md

EXPECTED_TABS = {"start", "patents", "fulltext", "evidence", "market", "reports", "settings"}


def test_all_tabs_in_overview() -> None:
  items = build_tab_overviews()
  tab_names = {item.tab_name for item in items}
  assert tab_names == EXPECTED_TABS


def test_overview_has_purpose_and_caveat() -> None:
  items = build_tab_overviews()
  for item in items:
    assert item.purpose.strip()
    assert item.caveat.strip()
    assert item.what_you_can_learn
    assert item.main_outputs


def test_overview_markdown_renders() -> None:
  md = render_overview_page_md()
  assert "まとめページ" in md
  assert "はじめる" in md
  assert "企業・市場シグナル" in md
  assert "FTO" in md or "final conclusion" in md.lower()
