"""Tests for weekly digest polish (Phase 24.1 / 24.1.1)."""

from __future__ import annotations

from tech_cartography.delivery.japanese_copy import build_digest_item_title
from tech_cartography.delivery.weekly_digest import (
  PREVIEW_ONLY_NOTICE,
  select_diverse_top_watch_items,
  truncate_at_sentence_boundary,
)


def _sample_items() -> list[dict[str, str]]:
  return [
    {
      "watch_theme": "CFRP / carbon fiber national project signal",
      "watch_type": "national_project_signal",
      "watch_priority": "high",
      "related_web_signal_title": "NEDO CFRP高レート生産技術開発",
      "related_web_signal_domain": "nedo.go.jp",
      "related_paper_title": "",
      "link_score": "0.9",
    },
    {
      "watch_theme": "CFRP / carbon fiber national project signal",
      "watch_type": "national_project_signal",
      "watch_priority": "high",
      "related_web_signal_title": "JST PAN系炭素繊維表面処理プロジェクト",
      "related_web_signal_domain": "jst.go.jp",
      "related_paper_title": "",
      "link_score": "0.85",
    },
    {
      "watch_theme": "CFRP / carbon fiber national project signal",
      "watch_type": "money_signal",
      "watch_priority": "medium",
      "related_web_signal_title": "NEDO 低コスト炭素繊維 / 水素タンク用途",
      "related_web_signal_domain": "nedo.go.jp",
      "related_paper_title": "",
      "link_score": "0.7",
    },
    {
      "watch_theme": "CFRP / carbon fiber national project signal",
      "watch_type": "patent_paper_web_signal",
      "watch_priority": "medium",
      "related_web_signal_title": "",
      "related_paper_title": "Carbon fiber surface treatment review",
      "link_score": "0.6",
    },
  ]


def test_select_diverse_top_watch_items_avoids_same_theme_only() -> None:
  selected = select_diverse_top_watch_items(_sample_items(), top_n=3)
  assert len(selected) == 3
  web_titles = [item.get("related_web_signal_title", "") for item in selected]
  assert len({title for title in web_titles if title}) >= 2


def test_select_diverse_top_watch_items_spreads_watch_type() -> None:
  selected = select_diverse_top_watch_items(_sample_items(), top_n=3)
  types = {item.get("watch_type") for item in selected}
  assert len(types) >= 2


def test_truncate_at_sentence_boundary_uses_japanese_period() -> None:
  text = "これは重要な監視候補です。次にNEDOの一次資料を確認してください。さらに詳細な確認が必要です。"
  result = truncate_at_sentence_boundary(text, max_chars=30)
  assert result.endswith("（要確認）")
  assert "確認" not in result[-20:] or "。" in result


def test_truncate_at_sentence_boundary_short_text_unchanged() -> None:
  assert truncate_at_sentence_boundary("短い文", max_chars=220) == "短い文"


def test_build_digest_item_title_uses_web_signal_source() -> None:
  item = _sample_items()[0]
  title = build_digest_item_title(item)
  assert "NEDO" in title
  assert "CFRP" in title or "高レート" in title


def test_build_digest_item_title_distinguishes_similar_themes() -> None:
  titles = [build_digest_item_title(item) for item in _sample_items()[:3]]
  assert len(set(titles)) == 3


def test_preview_only_notice_constant_legacy() -> None:
  assert "Preview only" in PREVIEW_ONLY_NOTICE
