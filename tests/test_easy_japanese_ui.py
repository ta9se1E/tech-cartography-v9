"""Tests for easy Japanese UI helpers."""

import pandas as pd

from tech_cartography.ui.easy_japanese_ui import (
  prepare_patent_display_df,
  render_evidence_validation_summary,
  render_fulltext_status_card,
  render_fulltext_vs_watch_notice,
  render_manual_checklist_notice,
  render_patent_card,
  render_strategic_watch_card,
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


def test_strategic_watch_japanese_display() -> None:
  df = pd.DataFrame(
    [
      {
        "publication_number": "CN-2024-000001",
        "title": "PAN carbon fiber",
        "assignee": "ZHONGFU SHENYING CARBON FIBER CO LTD",
        "country": "CN",
        "watch_reason_japanese": "中複神鷹系の出願",
        "manual_route_reason": "CN公報のためPDF確認",
        "recommended_next_action_japanese": "PDFで手動確認",
      },
    ],
  )
  display = prepare_patent_display_df(df)
  assert "監視理由" in display.columns
  card = render_strategic_watch_card(df.iloc[0].to_dict())
  assert "中複神鷹" in card or "PDF" in card


def test_china_not_excluded_notice() -> None:
  notice = render_fulltext_vs_watch_notice()
  assert "中国候補を除外しているわけではありません" in notice
  assert "手動確認" in notice or "PDF" in notice


def test_fulltext_status_japanese_display() -> None:
  card = render_fulltext_status_card(
    {
      "title": "PAN carbon fiber",
      "publication_number": "US-12565719-B2",
      "retrieval_status": "dry_run_only",
      "evidence_level": "metadata_only",
    },
  )
  assert "ドライラン" in card
  assert "根拠レベル" in card


def test_manual_checklist_notice_text() -> None:
  notice = render_manual_checklist_notice()
  assert "中国候補を除外しているわけではありません" in notice


def test_evidence_validation_japanese_summary() -> None:
  summary = {
    "summary": {
      "fulltext_records": 5,
      "ready_for_claim_extraction": 0,
      "dry_run_only": 5,
      "manual_required": 2,
      "generated_claim_elements": 0,
      "generated_paper_queries": 0,
      "openalex_mode": "plan_only",
    },
    "recommended_actions": ["US候補に対して execute-fulltext を実行する"],
  }
  html = render_evidence_validation_summary(summary)
  assert "全文が取れた特許だけ" in html
  assert "dry-run" in html or "ドライラン" in html or "dry_run" in html.lower()
  assert "中国候補" in html
  assert "裏取り候補" in html
  assert "execute-fulltext" in html
