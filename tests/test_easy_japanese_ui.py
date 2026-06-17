"""Tests for easy Japanese UI helpers."""

import pandas as pd

from tech_cartography.ui.easy_japanese_ui import (
  prepare_patent_display_df,
  render_acquisition_policy_summary,
  render_claims_paper_query_plan_card,
  render_claim_paper_candidate_map_card,
  render_cost_ledger_debug,
  render_evidence_validation_summary,
  render_evidence_map_synthesis_card,
  render_openalex_limited_execution_card,
  render_paper_candidate_relevance_card,
  render_fulltext_availability_notice,
  render_fulltext_execute_summary,
  render_fulltext_status_card,
  render_fulltext_vs_watch_notice,
  render_manual_checklist_notice,
  render_manual_fulltext_route_card,
  render_patent_card,
  render_strategic_watch_card,
  render_user_badge,
  render_watch_profile_card,
  render_weekly_digest_preview_block,
  summarize_stage_statuses,
)
from tech_cartography.ui.japanese_labels import (
  explain_cost_guard_status,
  explain_fulltext_scope,
  translate_fulltext_scope,
  translate_tab_name,
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


def test_fulltext_execute_summary_japanese() -> None:
  html = render_fulltext_execute_summary(
    {
      "selected_for_execute_count": 1,
      "estimated_mode": "execute",
      "confirmation_required": False,
      "fulltext_scope": "claims_only",
      "cost_guard_requires_expensive_confirmation": True,
      "recommended_expensive_command": "python scripts/run_carbon_fiber_evidence_map.py --allow-expensive-fulltext",
    },
    {"retrieved_count": 1, "skipped_not_selected_count": 4, "cache_hit_count": 0, "cost_guard_requires_expensive_count": 1},
  )
  assert "まず1件だけ" in html
  assert "中国候補" in html
  assert "請求項だけ" in html
  assert "allow-expensive-fulltext" in html
  assert "USD" in html or "GB上限" in html


def test_fulltext_execute_summary_claims_only_scope() -> None:
  html = render_fulltext_execute_summary(
    {"fulltext_scope": "claims_only", "estimated_mode": "dry_run"},
    {"fulltext_scope": "claims_only"},
  )
  assert "請求項だけ" in html
  assert "明細書は後で" in html


def test_fulltext_status_skipped_not_selected_japanese() -> None:
  card = render_fulltext_status_card(
    {
      "title": "Fiber",
      "publication_number": "US-2",
      "retrieval_status": "skipped_not_selected",
      "evidence_level": "metadata_only",
    },
  )
  assert "実行対象外" in card


def test_tab_labels_japanese() -> None:
  assert translate_tab_name("start") == "はじめる"
  assert translate_tab_name("fulltext") == "全文確認"
  assert translate_tab_name("settings") == "設定"


def test_fulltext_scope_labels() -> None:
  assert translate_fulltext_scope("claims_only") == "請求項だけ確認"
  assert "請求項" in explain_fulltext_scope("claims_only")


def test_cost_guard_explanation_japanese() -> None:
  text = explain_cost_guard_status("blocked_by_gb_but_usd_allowed_requires_confirmation")
  assert "データ量" in text or "金額" in text


def test_user_badge_and_watch_profile_helpers() -> None:
  badge = render_user_badge({"display_name": "太郎", "email": "t@example.com", "company_name": "ACME"})
  assert "太郎" in badge
  card = render_watch_profile_card({"theme": "PAN系", "keywords": ["PAN"], "companies": ["Toray"], "countries": ["US"]})
  assert "PAN" in card
  assert "Toray" in card


def test_streamlit_state_keys_are_separated() -> None:
  from tech_cartography.ui.streamlit_session import (
    STATE_PIPELINE_ROOT,
    STATE_SELECTED_RUN_ID,
    WIDGET_PIPELINE_ROOT,
    WIDGET_SELECTED_RUN_ID,
    assert_no_widget_internal_key_collision,
  )

  assert_no_widget_internal_key_collision()
  assert WIDGET_PIPELINE_ROOT != STATE_PIPELINE_ROOT
  assert WIDGET_SELECTED_RUN_ID != STATE_SELECTED_RUN_ID


def test_acquisition_policy_summary_ui_no_amounts() -> None:
  html = render_acquisition_policy_summary(
    {
      "user_facing_name_japanese": "標準監視モード",
      "user_facing_description_japanese": "広く監視します",
      "included_items": ["特許候補の更新"],
      "excluded_items": ["明細書全文"],
      "skipped_reason_japanese": "今回は標準監視のため全文取得は行いません",
      "manual_watch_count": 3,
      "selected_targets_count": 0,
    },
  )
  assert "標準監視モード" in html
  assert "usd" not in html.lower()
  assert "$" not in html
  assert "ドル" not in html


def test_weekly_digest_preview_ui() -> None:
  html = render_weekly_digest_preview_block(
    {
      "note_japanese": "プレビューです。メール送信はまだ行いません。",
      "acquisition_policy": {"name_japanese": "標準監視モード"},
      "important_patents": [],
      "china_strategic_watch": [{"publication_number": "CN-1"}],
      "us_deep_dive_candidates": [],
    },
  )
  assert "Weekly Digest Preview" in html
  assert "usd" not in html.lower()


def test_cost_ledger_debug_hidden_by_default() -> None:
  assert render_cost_ledger_debug(None) == ""
  html = render_cost_ledger_debug({"entry_count": 2, "retrieval_status_counts": {"dry_run_only": 2}})
  assert "開発者向け" in html
  assert "actual_total" not in html.lower()


def test_missing_internal_cost_policy_ui_does_not_crash() -> None:
  html = render_acquisition_policy_summary(None)
  assert "まだありません" in html
  digest = render_weekly_digest_preview_block(None)
  assert "まだありません" in digest


def test_manual_fulltext_route_card_shows_status_without_amounts() -> None:
  html = render_manual_fulltext_route_card(
    "US-12565719-B2",
    {
      "manual_input_exists": True,
      "claims_present": True,
      "description_present": False,
      "ready_for_claim_extraction": True,
      "route_label_japanese": "claims入力済み",
    },
    bigquery_not_found=True,
  )
  assert "Manual Route" in html
  assert "BigQuery public dataでは本文が確認できなかったため" in html
  assert "import_manual_fulltext.py" in html
  assert "Claim Element抽出に進める" in html
  assert "usd" not in html.lower()
  assert "$" not in html


def test_fulltext_availability_notice_bigquery_not_found() -> None:
  html = render_fulltext_availability_notice(
    {
      "publication_number": "US-12565719-B2",
      "retrieval_status": "not_found",
    },
  )
  assert "BigQuery側では請求項が確認できませんでした" in html
  assert "Google Patents" in html


def test_claims_paper_query_plan_card_shows_plan_only_caveat() -> None:
  html = render_claims_paper_query_plan_card(
    {
      "total_queries": 3,
      "openalex_mode": "plan_only",
      "confidence_levels": ["medium", "low"],
      "query_examples": [
        "polyacrylonitrile carbon fiber carbonization tensile strength modulus",
      ],
      "caveat_japanese": "請求項ベースの限定的な裏取り候補です。",
    },
    manual_claims_loaded=True,
  )
  assert "Claims-based Paper Query Plan" in html
  assert "plan_only" in html
  assert "supporting evidence candidate" in html
  assert "OpenAlex実行準備OK" in html or "要改善" in html
  assert "query type分布" in html
  assert "manual claims loaded" in html
  assert "usd" not in html.lower()
  assert "$" not in html


def test_claims_paper_query_quality_card_no_amounts() -> None:
  html = render_claims_paper_query_plan_card(
    {
      "total_queries": 6,
      "openalex_mode": "plan_only",
      "plan_ready_for_openalex": True,
      "quality_summary": {
        "plan_ready_for_openalex": True,
        "query_type_distribution": {"material_process": 2, "property_condition": 2},
        "confidence_distribution": {"medium": 4, "low": 2},
      },
      "query_type_distribution": {"material_process": 2, "property_condition": 2},
      "confidence_distribution": {"medium": 4, "low": 2},
      "query_examples": ["PAN carbon fiber carbonization"],
    },
  )
  assert "OpenAlex実行準備OK" in html
  assert "usd" not in html.lower()


def test_openalex_limited_execution_card_renders_without_amounts() -> None:
  html = render_openalex_limited_execution_card(
    {
      "mode": "execute",
      "execution_status": "success",
      "executed_queries_count": 2,
      "total_paper_records": 1,
      "cache_hits": 1,
      "selected_queries": [
        {"query_type": "material_process", "confidence": "medium", "query": "PAN carbon fiber"},
      ],
      "paper_records": [{"title": "Carbon fiber tensile strength study"}],
      "source_quality_results": [{"quality_level": "background", "source_id": "W1", "source_name": "Journal"}],
      "caveat_japanese": "論文候補は技術背景の裏取り候補です。",
    },
  )
  assert "OpenAlex Limited Execution" in html
  assert "supporting" in html.lower() or "裏取り候補" in html
  assert "$" not in html
  assert "usd" not in html.lower()


def test_claim_paper_candidate_map_card_renders_caveat() -> None:
  html = render_claim_paper_candidate_map_card(
    [
      {
        "element_type": "material",
        "paper_title": "PAN carbonization study",
        "link_type": "material_process_background",
        "confidence": "low",
      },
    ],
  )
  assert "Claim × Paper Candidate Map" in html
  assert "侵害性" in html or "裏取り候補" in html
  assert "$" not in html


def test_evidence_validation_summary_shows_openalex_limited() -> None:
  summary = {
    "summary": {
      "fulltext_records": 1,
      "openalex_mode": "execute",
      "openalex_paper_records": 2,
      "claim_paper_candidate_links": 3,
    },
    "openalex_limited_execution": {
      "mode": "execute",
      "executed_queries_count": 2,
      "total_paper_records": 2,
      "selected_queries": [{"query": "PAN carbon fiber", "query_type": "material_process", "confidence": "medium"}],
    },
    "claim_paper_candidate_links": {
      "representative_links": [
        {
          "element_type": "material",
          "paper_title": "Carbon fiber paper",
          "link_type": "material_process_background",
          "confidence": "low",
        },
      ],
    },
    "recommended_actions": [],
  }
  html = render_evidence_validation_summary(summary)
  assert "OpenAlex" in html
  assert "Claim × Paper" in html or "Claim×Paper" in html
  assert "$" not in html


def test_paper_candidate_relevance_card_renders_without_amounts() -> None:
  html = render_paper_candidate_relevance_card(
    {
      "total_paper_candidates": 5,
      "selected_evidence_papers": 2,
      "excluded_off_topic_count": 1,
      "broad_background_count": 2,
      "relevance_bucket_distribution": {
        "strong_material_process_background": 1,
        "broad_composite_background": 2,
      },
      "representative_selected_papers": [
        {"title": "PAN carbon fiber carbonization", "relevance_bucket": "strong_material_process_background", "relevance_score": 0.6},
      ],
      "excluded_broad_off_topic": [
        {"title": "Natural Fiber Reinforced Composites review", "relevance_bucket": "broad_composite_background"},
      ],
      "caveat_japanese": "広い複合材料レビューは背景候補として扱います。",
    },
  )
  assert "Paper Candidate Relevance Filter" in html
  assert "broad background" in html.lower() or "Broad background" in html
  assert "PAN carbon fiber" in html
  assert "$" not in html
  assert "usd" not in html.lower()


def test_evidence_summary_includes_relevance_filter() -> None:
  summary = {
    "summary": {"openalex_mode": "execute"},
    "paper_candidate_relevance": {
      "total_paper_candidates": 4,
      "selected_evidence_papers": 2,
      "excluded_off_topic_count": 1,
      "broad_background_count": 1,
      "representative_selected_papers": [
        {"title": "PAN carbon fiber", "relevance_bucket": "strong_material_process_background", "relevance_score": 0.5},
      ],
    },
    "recommended_actions": [],
  }
  html = render_evidence_validation_summary(summary)
  assert "Paper Candidate Relevance Filter" in html
  assert "$" not in html


def test_evidence_map_synthesis_card_renders() -> None:
  html = render_evidence_map_synthesis_card(
    {
      "publication_number": "US-12565719-B2",
      "title": "Carbon fiber",
      "synthesis_status": "ready_with_selected_papers",
      "claim_element_count": 2,
      "selected_evidence_paper_count": 3,
      "claim_paper_link_count": 2,
      "key_findings_japanese": ["PAN系炭素繊維の論文候補を選定"],
      "evidence_gaps_japanese": ["明細書未入力"],
      "next_actions_japanese": ["descriptionを追加"],
      "selected_evidence_papers": [
        {"title": "PAN carbon fiber carbonization", "relevance_bucket": "strong_material_process_background"},
      ],
      "evidence_map_items": [
        {
          "element_type": "material",
          "element_text": "PAN precursor",
          "best_paper_title": "PAN carbon fiber",
          "confidence": "low",
        },
      ],
      "caveats_japanese": ["supporting evidence candidate"],
    },
  )
  assert "Evidence Map Synthesis" in html
  assert "supporting evidence candidate" in html.lower()
  assert "PAN carbon fiber" in html
  assert "$" not in html


def test_evidence_summary_includes_synthesis_card() -> None:
  summary = {
    "summary": {"openalex_mode": "execute"},
    "evidence_map_synthesis": {
      "publication_number": "US-12565719-B2",
      "synthesis_status": "ready_with_selected_papers",
      "claim_element_count": 1,
      "selected_evidence_paper_count": 2,
      "key_findings_japanese": ["finding"],
    },
    "recommended_actions": [],
  }
  html = render_evidence_validation_summary(summary)
  assert "Evidence Map Synthesis" in html
  assert "$" not in html
