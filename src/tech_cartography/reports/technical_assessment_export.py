"""Export helpers for technical view assessment outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tech_cartography.reports.project_export import save_records_csv
from tech_cartography.reports.technical_view_report import (
  build_technical_view_summary,
  render_technical_view_markdown,
  save_technical_view_report,
)


def save_technical_view_outputs(result: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  summary = build_technical_view_summary(result)
  markdown = render_technical_view_markdown(summary)

  patent_rows = [
    {
      "publication_number": assessment.get("publication_number"),
      "patent_title": assessment.get("patent_title"),
      "assignee": assessment.get("assignee"),
      "overall_technical_score": assessment.get("overall_technical_score"),
      "overall_technical_confidence": assessment.get("overall_technical_confidence"),
      "technical_summary": assessment.get("technical_summary"),
      "recommended_reader_action": assessment.get("recommended_reader_action"),
      "strongest_supported_points": assessment.get("strongest_supported_points"),
      "weak_or_uncertain_points": assessment.get("weak_or_uncertain_points"),
      "key_evidence_gaps": assessment.get("key_evidence_gaps"),
    }
    for assessment in result.get("technical_assessments", [])
  ]

  paths = {
    "technical_assessments_json": str(out / "technical_assessments.json"),
    "technical_assessment_items_csv": save_records_csv(
      result.get("assessment_items", []),
      out / "technical_assessment_items.csv",
    ),
    "patent_technical_summary_csv": save_records_csv(
      patent_rows,
      out / "patent_technical_summary.csv",
    ),
    "common_technical_risks_json": str(out / "common_technical_risks.json"),
    "technical_view_report_md": save_technical_view_report(markdown, out),
  }

  with Path(paths["technical_assessments_json"]).open("w", encoding="utf-8") as handle:
    json.dump(result.get("technical_assessments", []), handle, indent=2, ensure_ascii=False)
  with Path(paths["common_technical_risks_json"]).open("w", encoding="utf-8") as handle:
    json.dump(
      {
        "common_technical_risks": result.get("common_technical_risks", {}),
        "common_evidence_gaps": result.get("common_evidence_gaps", {}),
      },
      handle,
      indent=2,
      ensure_ascii=False,
    )
  paths["output_dir"] = str(out)
  return paths
