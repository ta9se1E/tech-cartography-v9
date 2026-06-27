"""Claim batch import export (Phase 27Q.1)."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from tech_cartography.runtime.v8_claim_batch_import_schema import ClaimBatchImportReport
from tech_cartography.services.v8_sources_table import project_root_from_here

LOCAL_CLAIM_BATCH_IMPORT = "local_v8_claim_batch_import"


def get_claim_batch_import_dir(project_root: Path | str | None = None) -> Path:
  root = Path(project_root or project_root_from_here())
  return root / "outputs" / LOCAL_CLAIM_BATCH_IMPORT


def export_claim_batch_import_report(
  report: ClaimBatchImportReport,
  project_root: Path | str | None = None,
) -> Path:
  root = Path(project_root or project_root_from_here())
  out_dir = get_claim_batch_import_dir(root) / report.case_id / report.report_id
  out_dir.mkdir(parents=True, exist_ok=True)

  json_path = out_dir / "claim_batch_import_report.json"
  json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

  md_lines = [
    f"# Claim Batch Import — {report.case_id}",
    "",
    f"- mode: {report.mode}",
    f"- duplicate_mode: {report.duplicate_mode}",
    f"- total_rows: {report.total_rows}",
    f"- valid_rows: {report.valid_rows}",
    f"- rejected_rows: {report.rejected_rows}",
    f"- applied_rows: {report.applied_rows}",
    "",
    "claim 本文はユーザー提供のみ — 自動生成しません。",
    "",
  ]
  (out_dir / "claim_batch_import_report.md").write_text("\n".join(md_lines), encoding="utf-8")

  preview_cols = ["publication_number", "claim_no", "claim_text", "claim_source_type", "user_note"]
  preview_buf = io.StringIO()
  writer = csv.DictWriter(preview_buf, fieldnames=preview_cols)
  writer.writeheader()
  for row in report.rows:
    writer.writerow({c: getattr(row, c, "") for c in preview_cols})
  (out_dir / "claim_batch_import_preview.csv").write_text(preview_buf.getvalue(), encoding="utf-8")

  if report.rejected:
    rej_buf = io.StringIO()
    rej_writer = csv.DictWriter(rej_buf, fieldnames=["row_number", "publication_number", "claim_no", "reject_reason"])
    rej_writer.writeheader()
    for row in report.rejected:
      rej_writer.writerow({
        "row_number": row.row_number,
        "publication_number": row.publication_number,
        "claim_no": row.claim_no,
        "reject_reason": row.reject_reason,
      })
    (out_dir / "rejected_rows.csv").write_text(rej_buf.getvalue(), encoding="utf-8")

  return out_dir
