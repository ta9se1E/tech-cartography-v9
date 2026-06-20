"""Tests for web signal Japanese renderer (Phase 24.5B)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from tech_cartography.ui.label_renderer import translate_label
from tech_cartography.ui.web_signal_review_ui import (
  SIGNAL_INTRO_JA,
  SIGNAL_TOP_COLUMNS,
  SIGNAL_TOP_DISPLAY_LIMIT,
  prepare_signal_top_display_df,
)

UI_PATH = Path("src/tech_cartography/ui/web_signal_review_ui.py")


def test_signal_intro_japanese_text() -> None:
  text = UI_PATH.read_text(encoding="utf-8")
  assert "render_signal_intro_card" in text
  assert "確認候補" in SIGNAL_INTRO_JA
  assert "直接関係" in SIGNAL_INTRO_JA


def test_top_display_limits_to_five() -> None:
  rows = [
    {
      "source_title": f"Title {i}",
      "source_domain": "example.org",
      "signal_type": "national_project",
      "review_priority": 100 - i,
      "source_url": f"https://example.org/{i}",
      "next_verification_action": "confirm scope",
    }
    for i in range(10)
  ]
  df = pd.DataFrame(rows)
  top = prepare_signal_top_display_df(df, limit=SIGNAL_TOP_DISPLAY_LIMIT)
  assert len(top) == 5
  assert list(top.columns) == list(SIGNAL_TOP_COLUMNS)


def test_top_display_hides_signal_id_from_columns() -> None:
  top = prepare_signal_top_display_df(
    pd.DataFrame([{"signal_id": "sig-1", "source_title": "T", "source_domain": "d.org", "signal_type": "money"}]),
  )
  assert "signal_id" not in top.columns
  assert "batch_id" not in top.columns


def test_developer_expander_in_source() -> None:
  text = UI_PATH.read_text(encoding="utf-8")
  section = text.split("def _render_signal_top_table", 1)[1].split("def render_high_priority", 1)[0]
  assert "開発者向け" in section
  assert "SIGNAL_DEVELOPER_COLUMNS" in section


def test_english_summary_in_raw_expander() -> None:
  text = UI_PATH.read_text(encoding="utf-8")
  assert "英語詳細 / raw summary" in text


def test_translate_signal_type_labels() -> None:
  assert translate_label("national_project") == "国家プロジェクト候補"
  assert translate_label("money") == "公的予算・資金関連候補"
  assert translate_label("ir_disclosure") == "IR・開示候補"
