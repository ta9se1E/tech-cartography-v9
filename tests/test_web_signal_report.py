"""Tests for web signal report."""

from tech_cartography.evidence.web_signal_mapper import map_web_signals_to_patents
from tech_cartography.reports.web_signal_report import build_web_signal_summary, render_web_signal_markdown


def test_report_markdown_sections() -> None:
  result = map_web_signals_to_patents(
    [
      {
        "signal_id": "ws1",
        "company": "TORAY",
        "normalized_company": "TORAY",
        "source_title": "Prepreg expansion",
        "source_url": "https://www.toray.com/news/press-release",
        "source_name": "Press release",
        "signal_type": "production_expansion",
        "technology_terms": ["carbon fiber", "prepreg"],
        "business_signal": "Expansion",
        "display_url": "https://www.toray.com/news/press-release",
      },
    ],
    [
      {
        "publication_number": "US1",
        "title": "Carbon fiber prepreg",
        "assignee": "TORAY",
        "abstract": "prepreg aerospace carbon fiber",
        "primary_cluster_id": "bundle_prepreg",
      },
    ],
  )
  summary = build_web_signal_summary(result)
  markdown = render_web_signal_markdown(summary)
  assert "Web / Company Signal Mapping Report" in markdown
  assert "## 1. Summary" in markdown
  assert "## 2. Signals by Company" in markdown
  assert "## 6. Caveats" in markdown
