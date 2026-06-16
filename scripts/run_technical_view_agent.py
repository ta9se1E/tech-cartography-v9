#!/usr/bin/env python3
"""Run Technical View Agent on claim-paper evidence map outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.agents.technical_view_agent import run_technical_view_assessment
from tech_cartography.reports.project_export import build_output_directory, load_records_csv
from tech_cartography.reports.technical_assessment_export import save_technical_view_outputs
from tech_cartography.reports.technical_view_report import build_technical_view_summary


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Run Technical View Agent")
  parser.add_argument("--patent-evidence-maps-json", required=True)
  parser.add_argument("--evidence-items-csv", required=True)
  parser.add_argument("--evidence-gaps-csv", required=True)
  parser.add_argument("--claim-elements-csv", default="")
  parser.add_argument("--fulltext-records-json", default="")
  parser.add_argument("--output-dir", default="outputs/technical_view_assessment")
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


def _load_json_list(path: Path) -> list[dict]:
  with path.open(encoding="utf-8") as handle:
    data = json.load(handle)
  if isinstance(data, list):
    return data
  if isinstance(data, dict) and isinstance(data.get("patent_evidence_maps"), list):
    return data["patent_evidence_maps"]
  return []


def main() -> int:
  args = parse_args()
  maps_path = _resolve_latest(Path(args.patent_evidence_maps_json), "patent_evidence_maps.json")
  items_path = _resolve_latest(Path(args.evidence_items_csv), "claim_paper_evidence_items.csv")
  gaps_path = _resolve_latest(Path(args.evidence_gaps_csv), "evidence_gaps.csv")
  claim_path = (
    _resolve_latest(Path(args.claim_elements_csv), "claim_elements.csv")
    if args.claim_elements_csv
    else Path("")
  )
  fulltext_path = (
    _resolve_latest(Path(args.fulltext_records_json), "top5_fulltext_records.json")
    if args.fulltext_records_json
    else Path("")
  )

  patent_maps = _load_json_list(maps_path) if maps_path.exists() else []
  evidence_items = load_records_csv(items_path) if items_path.exists() else []
  evidence_gaps = load_records_csv(gaps_path) if gaps_path.exists() else []
  claim_elements = load_records_csv(claim_path) if claim_path and claim_path.exists() else None
  fulltext_records = _load_json_list(fulltext_path) if fulltext_path and fulltext_path.exists() else None

  result = run_technical_view_assessment(
    patent_maps,
    evidence_items,
    evidence_gaps,
    claim_elements=claim_elements,
    fulltext_records=fulltext_records,
  )
  output_dir = build_output_directory(args.output_dir)
  paths = save_technical_view_outputs(result, output_dir)
  payload = {
    "patent_evidence_maps_json": str(maps_path),
    "evidence_items_csv": str(items_path),
    "evidence_gaps_csv": str(gaps_path),
    "paths": paths,
    "summary": build_technical_view_summary(result),
  }
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
