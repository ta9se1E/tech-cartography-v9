"""Export helpers for synthesis report outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tech_cartography.domain.synthesis_report import SynthesisReport
from tech_cartography.reports.project_export import save_records_csv
from tech_cartography.reports.synthesis_report import (
  build_synthesis_report_summary,
  render_synthesis_markdown,
  save_synthesis_report,
)


def save_synthesis_outputs(result: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  summary = build_synthesis_report_summary(result)
  markdown = render_synthesis_markdown(summary)

  report_payload = SynthesisReport.from_dict(result).to_dict()
  synthesis_json_path = out / "synthesis_report.json"
  with synthesis_json_path.open("w", encoding="utf-8") as handle:
    json.dump(report_payload, handle, indent=2, ensure_ascii=False)

  key_findings_rows = [
    {
      "finding_id": finding.get("finding_id"),
      "finding_type": finding.get("finding_type"),
      "title": finding.get("title"),
      "summary": finding.get("summary"),
      "importance": finding.get("importance"),
      "confidence": finding.get("confidence"),
      "related_publications": finding.get("related_publications"),
      "related_companies": finding.get("related_companies"),
      "evidence_basis": finding.get("evidence_basis"),
      "recommended_next_action": finding.get("recommended_next_action"),
    }
    for finding in result.get("key_findings", [])
  ]

  sme_rows = [
    {
      "action_category": section.get("action_category"),
      "items": section.get("items"),
    }
    for section in result.get("sme_action_plan", [])
  ]

  next_update_path = out / "next_update_recommendations.json"
  with next_update_path.open("w", encoding="utf-8") as handle:
    json.dump(
      {"next_update_recommendations": result.get("next_update_recommendations", [])},
      handle,
      indent=2,
      ensure_ascii=False,
    )

  paths = {
    "synthesis_report_json": str(synthesis_json_path),
    "key_findings_csv": save_records_csv(key_findings_rows, out / "key_findings.csv"),
    "priority_patents_csv": save_records_csv(result.get("priority_patents", []), out / "priority_patents.csv"),
    "sme_action_plan_csv": save_records_csv(sme_rows, out / "sme_action_plan.csv"),
    "next_update_recommendations_json": str(next_update_path),
    "carbon_fiber_evidence_map_md": save_synthesis_report(markdown, out),
    "output_dir": str(out),
  }
  return paths
