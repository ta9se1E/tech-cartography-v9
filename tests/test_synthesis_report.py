"""Tests for synthesis report and export."""

import json
from pathlib import Path

from tech_cartography.agents.synthesis_agent import run_synthesis_report
from tech_cartography.reports.synthesis_export import save_synthesis_outputs
from tech_cartography.reports.synthesis_report import (
  build_synthesis_report_summary,
  render_synthesis_markdown,
)


def _minimal_result() -> dict:
  return run_synthesis_report(
    [
      {
        "cluster_id": "bundle_prepreg",
        "name": "bundle_prepreg",
        "patent_count": 3,
        "representative_terms": ["prepreg"],
        "top_assignees": ["TORAY"],
        "representative_patents": ["US1"],
      },
    ],
    [
      {
        "publication_number": "US1",
        "title": "Carbon fiber prepreg",
        "assignee": "TORAY",
        "primary_cluster_id": "bundle_prepreg",
        "rank": 1,
      },
    ],
    [{"publication_number": "US1"}],
    [{"publication_number": "US1", "overall_technical_confidence": "high"}],
    [
      {
        "publication_number": "US1",
        "overall_technical_confidence": "high",
        "strongest_supported_points": ["interface"],
      },
    ],
    [
      {
        "publication_number": "US1",
        "overall_business_confidence": "high",
        "commercialization_signals": ["signal candidate"],
        "recommended_reader_action": "monitor_company_signals",
      },
    ],
    [{"publication_number": "US1", "overall_business_confidence": "high"}],
    theme="PAN系炭素繊維",
  )


def test_report_markdown_sections() -> None:
  result = _minimal_result()
  summary = build_synthesis_report_summary(result)
  markdown = render_synthesis_markdown(summary)
  assert "## 1. Executive Summary" in markdown
  assert "## 3. Key Findings" in markdown
  assert "## 8. SME Action Plan" in markdown
  assert "## 11. Caveats" in markdown
  assert any("FTO" in line for line in markdown.splitlines())


def test_synthesis_export_writes_files(tmp_path: Path) -> None:
  result = _minimal_result()
  paths = save_synthesis_outputs(result, tmp_path)
  assert Path(paths["synthesis_report_json"]).exists()
  assert Path(paths["key_findings_csv"]).exists()
  assert Path(paths["priority_patents_csv"]).exists()
  assert Path(paths["sme_action_plan_csv"]).exists()
  assert Path(paths["next_update_recommendations_json"]).exists()
  assert Path(paths["carbon_fiber_evidence_map_md"]).exists()
  with Path(paths["synthesis_report_json"]).open(encoding="utf-8") as handle:
    payload = json.load(handle)
  assert payload.get("executive_summary")
