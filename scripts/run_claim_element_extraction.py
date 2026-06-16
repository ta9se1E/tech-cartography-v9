#!/usr/bin/env python3
"""Run claim element extraction on Top5 full text records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.reports.claim_element_pipeline import (
  run_claim_element_pipeline,
  save_claim_element_outputs,
)
from tech_cartography.reports.claim_element_report import build_claim_element_summary
from tech_cartography.reports.project_export import build_output_directory


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Extract claim elements from full text records")
  parser.add_argument("--input-json", required=True)
  parser.add_argument("--output-dir", default="outputs/claim_element_extraction")
  return parser.parse_args()


def _load_records(path: Path) -> list[dict]:
  with path.open(encoding="utf-8") as handle:
    data = json.load(handle)
  if isinstance(data, list):
    return data
  if isinstance(data, dict) and isinstance(data.get("retrieved_records"), list):
    return data["retrieved_records"]
  return []


def main() -> int:
  args = parse_args()
  input_path = Path(args.input_json)
  if not input_path.exists() and "latest" in str(input_path):
    parent = input_path.parent.parent
    candidates = sorted(parent.glob("*/top5_fulltext_records.json"))
    if candidates:
      input_path = candidates[-1]

  records = _load_records(input_path)
  result = run_claim_element_pipeline(records)
  output_dir = build_output_directory(args.output_dir)
  paths = save_claim_element_outputs(result, output_dir)
  payload = {
    "input_json": str(input_path),
    "paths": paths,
    "summary": build_claim_element_summary(result),
  }
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
