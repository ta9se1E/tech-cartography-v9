"""Tests for full text evidence report."""

from tech_cartography.reports.fulltext_evidence_report import (
  build_fulltext_evidence_summary,
  render_fulltext_evidence_markdown,
)


def test_report_markdown_sections() -> None:
  result = {
    "total_top5_candidates": 2,
    "total_candidates": 2,
    "us_fulltext_targets": 1,
    "us_fulltext_candidates": 1,
    "manual_required_candidates": 1,
    "manual_required_count": 0,
    "strategic_watch_manual_count": 1,
    "cn_watch_count": 1,
    "cache_hit_count": 0,
    "cache_hits": 0,
    "dry_run_only_count": 1,
    "retrieved_count": 0,
    "blocked_by_cost_guard": 0,
    "cost_guard_status": "ok",
    "total_estimated_gb": 0.1,
    "total_estimated_usd": 0.5,
    "maximum_bytes_billed_gb": 50.0,
    "mode": "dry_run",
    "retrieved_records": [
      {
        "publication_number": "US2024000001A1",
        "title": "PAN carbon fiber",
        "assignee": "Toray",
        "country": "US",
        "source_route": "us_bigquery_fulltext_candidate",
        "evidence_level": "metadata_only",
        "evidence_coverage": {
          "has_claims": False,
          "has_description": False,
        },
        "retrieval_status": "dry_run_only",
        "claims_source": "not_fetched",
        "description_source": "not_fetched",
      },
    ],
    "manual_required_rows": [],
    "strategic_watch_manual_rows": [
      {
        "publication_number": "CN-121137864-A",
        "title": "PAN carbon fiber CN",
        "country": "CN",
        "assignee": "ZHONGFU SHENYING CARBON FIBER CO LTD",
        "watch_reason_japanese": "中国炭素繊維有力企業",
      },
    ],
    "manual_required_records": [],
    "plan": {"plan_summary": {"caveat_japanese": "test caveat"}},
  }
  summary = build_fulltext_evidence_summary(result)
  markdown = render_fulltext_evidence_markdown(summary)
  assert "Controlled Full Text Run" in markdown
  assert "Manual Full Text Required" in markdown
  assert "China / Non-US Strategic Watch Manual Checks" in markdown
  assert "Caveats" in markdown
  assert "ZHONGFU" in markdown or "CN-121137864-A" in markdown
