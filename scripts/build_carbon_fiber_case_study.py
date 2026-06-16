#!/usr/bin/env python3
"""Build carbon fiber case study from BigQuery light retrieval CSV."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.reports.case_study_pipeline import (
  run_case_study_pipeline,
  save_case_study_outputs,
)
from tech_cartography.reports.project_export import build_output_directory, load_records_csv


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Build carbon fiber evidence map case study")
  parser.add_argument("--input-csv", required=True)
  parser.add_argument(
    "--output-dir",
    default="outputs/carbon_fiber_case_study",
  )
  parser.add_argument("--top-n", type=int, default=20)
  parser.add_argument("--fulltext-top-n", type=int, default=5)
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  input_path = Path(args.input_csv)
  if not input_path.exists() and "latest" in str(input_path):
    parent = input_path.parent.parent
    candidates = sorted(parent.glob("*/bigquery_light_results_dedup.csv"))
    if candidates:
      input_path = candidates[-1]

  records = load_records_csv(input_path)
  result = run_case_study_pipeline(
    records,
    top_n=args.top_n,
    fulltext_top_n=args.fulltext_top_n,
  )
  output_dir = build_output_directory(args.output_dir)
  paths = save_case_study_outputs(result, output_dir)
  payload = {
    "input_csv": str(input_path),
    "output_dir": str(output_dir),
    "record_count": len(records),
    "paths": paths,
    "summary": result["summary"],
  }
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
