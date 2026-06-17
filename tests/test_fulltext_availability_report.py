"""Tests for fulltext availability report (Phase 18A)."""

from __future__ import annotations

from tech_cartography.reports.fulltext_availability_report import (
  render_fulltext_availability_markdown,
  save_fulltext_availability_report,
)


def test_report_markdown_variants_and_no_usd(tmp_path) -> None:
  result = {
    "publication_number": "US-12565719-B2",
    "variants_checked": ["US-12565719-B2", "US12565719B2"],
    "probe_status": "not_found_in_bigquery",
    "matched_variant": "",
    "has_publication_row": False,
    "has_claims": False,
    "user_status_japanese": "BigQuery側では対象公報の行が見つかりませんでした。",
    "next_action_japanese": "Google Patentsで確認してください。",
    "internal_notes": ["format mismatch hypothesis"],
    "estimated_usd": 0.5,
  }
  md = render_fulltext_availability_markdown(result)
  assert "US-12565719-B2" in md
  assert "US12565719B2" in md
  assert "usd" not in md.lower()
  assert "$" not in md
  paths = save_fulltext_availability_report(result, tmp_path)
  assert paths["fulltext_availability_probe_md"]
