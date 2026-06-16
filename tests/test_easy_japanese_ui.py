"""Tests for easy Japanese UI helpers."""

import pandas as pd

from tech_cartography.ui.easy_japanese_ui import (
  prepare_patent_display_df,
  render_patent_card,
  summarize_stage_statuses,
)


def test_prepare_patent_display_df_adds_japanese_columns() -> None:
  df = pd.DataFrame(
    [
      {
        "publication_number": "US-2024-000001",
        "title": "PAN carbon fiber",
        "assignee": "Toray",
        "country": "US",
        "primary_cluster_id": "core_manufacturing",
        "total_score": 0.8,
        "noise_score": 0.1,
        "source_route": "us_bigquery_fulltext_candidate",
      },
    ],
  )
  display = prepare_patent_display_df(df)
  assert "公開番号" in display.columns
  assert "技術分類" in display.columns
  assert "全文確認ルート" in display.columns


def test_summarize_stage_statuses_japanese() -> None:
  manifest = {
    "stage_results": [
      {"stage_id": "search_strategy", "status": "success"},
      {"stage_id": "technology_clustering_ranking", "status": "blocked"},
    ],
  }
  rows = summarize_stage_statuses(manifest)
  assert len(rows) == 2
  assert rows[0]["状態"] == "成功"
  assert rows[1]["状態"] == "保留"


def test_missing_artifact_ui_helpers_do_not_crash() -> None:
  display = prepare_patent_display_df(pd.DataFrame())
  assert display.empty
  assert summarize_stage_statuses(None) == []
  card = render_patent_card({})
  assert "タイトル不明" in card or "—" in card
