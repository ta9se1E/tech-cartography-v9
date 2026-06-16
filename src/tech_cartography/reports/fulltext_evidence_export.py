"""Export helpers for controlled full text collection outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tech_cartography.reports.project_export import save_records_csv, save_retrieval_summary, save_summary_csv


def save_controlled_fulltext_outputs(
  output_dir: str | Path,
  *,
  plan: dict[str, Any],
  result: dict[str, Any],
  markdown: str,
  checklist_md: str,
  use_timestamp_subdir: bool = False,
) -> dict[str, str]:
  out = Path(output_dir)
  if use_timestamp_subdir:
    from tech_cartography.reports.project_export import build_output_directory

    out = build_output_directory(output_dir)
  else:
    out.mkdir(parents=True, exist_ok=True)

  paths: dict[str, str] = {}

  plan_path = out / "fulltext_plan.json"
  plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
  paths["fulltext_plan_json"] = str(plan_path)

  records = result.get("retrieved_records", [])
  records_json = out / "top5_fulltext_records.json"
  records_json.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
  paths["top5_fulltext_records_json"] = str(records_json)
  paths["top5_fulltext_records_csv"] = save_records_csv(records, out / "top5_fulltext_records.csv")

  manual_rows = result.get("manual_required_rows", [])
  paths["manual_fulltext_required_csv"] = save_summary_csv(
    manual_rows,
    out / "manual_fulltext_required.csv",
  )

  strategic_rows = result.get("strategic_watch_manual_rows", [])
  paths["strategic_watch_manual_fulltext_required_csv"] = save_summary_csv(
    strategic_rows,
    out / "strategic_watch_manual_fulltext_required.csv",
  )

  checklist_path = out / "manual_fulltext_checklist.md"
  checklist_path.write_text(checklist_md, encoding="utf-8")
  paths["manual_fulltext_checklist_md"] = str(checklist_path)

  summary = result.get("summary", result)
  paths["fulltext_retrieval_summary_json"] = save_retrieval_summary(
    summary,
    out / "fulltext_retrieval_summary.json",
  )

  execute_preview = result.get("execute_preview", {})
  preview_path = out / "fulltext_execute_preview.json"
  preview_path.write_text(json.dumps(execute_preview, indent=2, ensure_ascii=False), encoding="utf-8")
  paths["fulltext_execute_preview_json"] = str(preview_path)

  execute_results = result.get("execute_results", [])
  paths["fulltext_execute_results_csv"] = save_records_csv(
    execute_results,
    out / "fulltext_execute_results.csv",
  )

  report_path = out / "fulltext_evidence_report.md"
  report_path.write_text(markdown, encoding="utf-8")
  paths["fulltext_evidence_report_md"] = str(report_path)

  paths["output_dir"] = str(out)
  return paths
