#!/usr/bin/env python3
"""Run Carbon Fiber Evidence Map v1 pipeline (Phase 12)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.orchestration.case_study_runner import run_carbon_fiber_evidence_map_pipeline
from tech_cartography.orchestration.pipeline_config import PipelineConfig


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Run Carbon Fiber Evidence Map v1 pipeline")
  parser.add_argument("--config", default="configs/carbon_fiber_pipeline.yaml")

  parser.add_argument("--execute-bigquery", action="store_true", default=False)
  parser.add_argument("--execute-fulltext", action="store_true", default=False)
  parser.add_argument("--execute-openalex", action="store_true", default=False)

  parser.add_argument("--use-existing-light-csv", default="")
  parser.add_argument("--use-existing-top5-csv", default="")
  parser.add_argument("--web-signal-file", default="")

  parser.add_argument("--start-stage", default="")
  parser.add_argument("--stop-stage", default="")
  parser.add_argument("--skip-stage", action="append", default=[])
  parser.add_argument("--run-name", default="")
  parser.add_argument("--output-root", default="")
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  config = PipelineConfig.from_yaml(args.config)

  if args.execute_bigquery:
    config.execute_bigquery = True
  if args.execute_fulltext:
    config.execute_fulltext = True
  if args.execute_openalex:
    config.execute_openalex = True

  if args.use_existing_light_csv:
    config.use_existing_light_csv = args.use_existing_light_csv
  if args.use_existing_top5_csv:
    config.use_existing_top5_csv = args.use_existing_top5_csv
  if args.web_signal_file:
    config.web_signal_file = args.web_signal_file

  if args.start_stage:
    config.start_stage = args.start_stage
  if args.stop_stage:
    config.stop_stage = args.stop_stage
  if args.skip_stage:
    config.skip_stages = list(set((config.skip_stages or []) + list(args.skip_stage)))
  if args.run_name:
    config.run_name = args.run_name
  if args.output_root:
    config.output_root = args.output_root

  result = run_carbon_fiber_evidence_map_pipeline(config)
  payload = {
    "run_id": result.get("run_id"),
    "manifest_path": result.get("manifest_path"),
    "final_report_path": result.get("final_report_path"),
    "artifact_index_path": result.get("artifact_index_path"),
    "stage_statuses": result.get("stage_statuses"),
  }
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())

