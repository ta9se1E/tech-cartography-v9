"""Export helpers for business view assessment outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tech_cartography.reports.business_view_report import (
  build_business_view_summary,
  render_business_view_markdown,
  save_business_view_report,
)
from tech_cartography.reports.project_export import save_records_csv


def save_business_view_outputs(result: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  summary = build_business_view_summary(result)
  markdown = render_business_view_markdown(summary)

  patent_rows = [
    {
      "publication_number": assessment.get("publication_number"),
      "patent_title": assessment.get("patent_title"),
      "assignee": assessment.get("assignee"),
      "primary_cluster_id": assessment.get("primary_cluster_id"),
      "primary_cluster_name": assessment.get("primary_cluster_name"),
      "overall_business_score": assessment.get("overall_business_score"),
      "overall_business_confidence": assessment.get("overall_business_confidence"),
      "business_summary": assessment.get("business_summary"),
      "recommended_reader_action": assessment.get("recommended_reader_action"),
      "commercialization_signals": assessment.get("commercialization_signals"),
      "sme_opportunity_points": assessment.get("sme_opportunity_points"),
      "design_around_or_differentiation_hints": assessment.get("design_around_or_differentiation_hints"),
    }
    for assessment in result.get("business_assessments", [])
  ]

  paths = {
    "business_assessments_json": str(out / "business_assessments.json"),
    "business_assessment_items_csv": save_records_csv(
      result.get("assessment_items", []),
      out / "business_assessment_items.csv",
    ),
    "patent_business_summary_csv": save_records_csv(
      patent_rows,
      out / "patent_business_summary.csv",
    ),
    "sme_opportunity_candidates_csv": save_records_csv(
      result.get("sme_opportunity_candidates", []),
      out / "sme_opportunity_candidates.csv",
    ),
    "design_around_candidates_csv": save_records_csv(
      result.get("design_around_candidates", []),
      out / "design_around_candidates.csv",
    ),
    "common_business_risks_json": str(out / "common_business_risks.json"),
    "business_view_report_md": save_business_view_report(markdown, out),
  }

  with Path(paths["business_assessments_json"]).open("w", encoding="utf-8") as handle:
    json.dump(result.get("business_assessments", []), handle, indent=2, ensure_ascii=False)
  with Path(paths["common_business_risks_json"]).open("w", encoding="utf-8") as handle:
    json.dump(
      {
        "common_business_risks": result.get("common_business_risks", {}),
        "common_business_signals": result.get("common_business_signals", {}),
      },
      handle,
      indent=2,
      ensure_ascii=False,
    )
  paths["output_dir"] = str(out)
  return paths
