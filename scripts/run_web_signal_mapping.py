#!/usr/bin/env python3
"""Run web / company signal mapping against patent records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.reports.project_export import build_output_directory, load_records_csv
from tech_cartography.reports.web_signal_export import run_web_signal_mapping, save_web_signal_outputs
from tech_cartography.reports.web_signal_report import build_web_signal_summary
from tech_cartography.ingestion.web_signal_loader import load_web_signal_file


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Map web/company signals to patents")
  parser.add_argument(
    "--web-signal-file",
    default="case_studies/carbon_fiber/web_signals/carbon_fiber_web_signals_template.csv",
  )
  parser.add_argument(
    "--patents-csv",
    default="outputs/carbon_fiber_case_study/latest/top20_patents.csv",
  )
  parser.add_argument("--output-dir", default="outputs/web_signal_mapping")
  return parser.parse_args()


def _resolve_latest(path: Path, pattern: str) -> Path:
  if path.exists():
    return path
  if "latest" in str(path):
    parent = path.parent.parent
    candidates = sorted(parent.glob(f"*/{pattern}"))
    if candidates:
      return candidates[-1]
  return path


def main() -> int:
  args = parse_args()
  signal_path = Path(args.web_signal_file)
  if not signal_path.exists():
    signal_path = PROJECT_ROOT / args.web_signal_file
  patents_path = _resolve_latest(Path(args.patents_csv), Path(args.patents_csv).name)

  signals = load_web_signal_file(str(signal_path)) if signal_path.exists() else []
  patents = load_records_csv(patents_path) if patents_path.exists() else []

  result = run_web_signal_mapping(signals, patents)
  output_dir = build_output_directory(args.output_dir)
  paths = save_web_signal_outputs(result, output_dir)
  payload = {
    "web_signal_file": str(signal_path),
    "patents_csv": str(patents_path),
    "paths": paths,
    "summary": build_web_signal_summary(result),
  }
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
