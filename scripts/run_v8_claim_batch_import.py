#!/usr/bin/env python3
"""Claim batch import CLI (Phase 27Q.1)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
  sys.path.insert(0, str(SRC))

from tech_cartography.services.v8_claim_batch_import import (
  apply_claim_batch_import,
  validate_claim_batch_import,
)
from tech_cartography.services.v8_claim_batch_import_export import export_claim_batch_import_report


def main() -> int:
  parser = argparse.ArgumentParser(description="Claim CSV/Excel batch import")
  parser.add_argument("--case-id", required=True)
  parser.add_argument("--input-file", required=True)
  parser.add_argument("--mode", choices=["validate", "apply"], default="validate")
  parser.add_argument("--duplicate-mode", choices=["update", "skip", "append"], default="update")
  args = parser.parse_args()

  input_path = Path(args.input_file)
  if not input_path.exists():
    print(f"input not found: {input_path}", file=sys.stderr)
    return 1

  if args.mode == "validate":
    report = validate_claim_batch_import(
      case_id=args.case_id,
      input_path=input_path,
      duplicate_mode=args.duplicate_mode,
      project_root=PROJECT_ROOT,
    )
  else:
    report = apply_claim_batch_import(
      case_id=args.case_id,
      input_path=input_path,
      duplicate_mode=args.duplicate_mode,
      project_root=PROJECT_ROOT,
    )

  out_dir = export_claim_batch_import_report(report, project_root=PROJECT_ROOT)
  print(f"case_id: {report.case_id}")
  print(f"mode: {report.mode}")
  print(f"total_rows: {report.total_rows}")
  print(f"valid_rows: {report.valid_rows}")
  print(f"rejected_rows: {report.rejected_rows}")
  print(f"applied_rows: {report.applied_rows}")
  print(f"output_dir: {out_dir}")
  if report.backup_path:
    print(f"backup_path: {report.backup_path}")
  if report.updated_claims_input_path:
    print(f"claims_input: {report.updated_claims_input_path}")
  for row in report.rejected[:5]:
    print(f"rejected: row {row.row_number} {row.publication_number} — {row.reject_reason}")
  return 0 if report.valid_rows > 0 or args.mode == "validate" else 1


if __name__ == "__main__":
  sys.exit(main())
