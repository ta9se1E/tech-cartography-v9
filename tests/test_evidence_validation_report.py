from __future__ import annotations

from tech_cartography.reports.evidence_validation_report import (
  build_evidence_validation_summary,
  render_evidence_validation_markdown,
)


def test_report_contains_required_sections() -> None:
  result = {
    "status": "limited_no_fulltext",
    "fulltext_readiness": {
      "total_records": 1,
      "ready_count": 0,
      "limited_count": 0,
      "dry_run_only_count": 1,
      "manual_required_count": 1,
      "classified_records": [
        {
          "publication_number": "US-1",
          "title": "Fiber",
          "country": "US",
          "retrieval_status": "dry_run_only",
          "evidence_level": "metadata_only",
          "readiness_status": "dry_run_only",
        },
      ],
      "next_actions": [
        {"action_id": "execute_fulltext_for_us_targets", "reason": "dry-run"},
      ],
    },
    "claim_element_result": {"elements": [], "paper_queries": [], "record_results": []},
    "paper_query_result": {"total_queries": 0, "queries": []},
    "openalex_result": {"mode": "plan_only", "executed_queries": 0, "cache_hits": 0, "query_plan": [], "papers_dedup": []},
    "paper_evidence_result": {"evidence_links": [], "source_quality_results": []},
    "claim_paper_map_result": {"evidence_items": [], "evidence_gaps": []},
    "manual_candidates": [
      {"publication_number": "CN-1", "country": "CN", "title": "Zhongfu Shenying fiber", "assignee": "ZHONGFU"},
    ],
    "warnings": [],
    "errors": [],
  }
  summary = build_evidence_validation_summary(result)
  markdown = render_evidence_validation_markdown(summary)
  for heading in [
    "# Evidence Validation Report",
    "## 1. Summary",
    "## 2. Full Text Readiness",
    "## 5. China / Non-US Manual Watch",
    "## 8. Caveats",
  ]:
    assert heading in markdown
  assert "execute-fulltext" in markdown or "execute_fulltext_for_us_targets" in markdown
