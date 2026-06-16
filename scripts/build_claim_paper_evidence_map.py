#!/usr/bin/env python3
"""Build Patent Claim × Paper Evidence Map."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.evidence.claim_paper_evidence_map import build_claim_paper_evidence_map
from tech_cartography.reports.claim_paper_evidence_map_report import build_claim_paper_evidence_map_summary
from tech_cartography.reports.evidence_map_export import save_claim_paper_evidence_map_outputs
from tech_cartography.reports.project_export import build_output_directory, load_records_csv


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Build claim × paper evidence map")
  parser.add_argument("--claim-elements-csv", required=True)
  parser.add_argument("--paper-links-csv", required=True)
  parser.add_argument("--paper-records-csv", default="")
  parser.add_argument("--source-quality-csv", default="")
  parser.add_argument("--output-dir", default="outputs/claim_paper_evidence_map")
  parser.add_argument("--top-n", type=int, default=30)
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
  claim_path = _resolve_latest(Path(args.claim_elements_csv), "claim_elements.csv")
  links_path = _resolve_latest(Path(args.paper_links_csv), "paper_evidence_links.csv")
  records_path = (
    _resolve_latest(Path(args.paper_records_csv), "paper_records_dedup.csv")
    if args.paper_records_csv
    else links_path.parent / "paper_records_dedup.csv"
  )
  quality_path = (
    _resolve_latest(Path(args.source_quality_csv), "source_quality_results.csv")
    if args.source_quality_csv
    else links_path.parent / "source_quality_results.csv"
  )

  claim_elements = load_records_csv(claim_path) if claim_path.exists() else []
  paper_links = load_records_csv(links_path) if links_path.exists() else []
  paper_records = load_records_csv(records_path) if records_path.exists() else []
  source_quality = load_records_csv(quality_path) if quality_path.exists() else []

  result = build_claim_paper_evidence_map(
    claim_elements,
    paper_links,
    paper_records=paper_records,
    source_quality_results=source_quality,
  )
  result["top_evidence_items"] = result.get("top_evidence_items", [])[: args.top_n]
  output_dir = build_output_directory(args.output_dir)
  paths = save_claim_paper_evidence_map_outputs(result, output_dir, top_n=args.top_n)
  payload = {
    "claim_elements_csv": str(claim_path),
    "paper_links_csv": str(links_path),
    "paper_records_csv": str(records_path),
    "source_quality_csv": str(quality_path),
    "paths": paths,
    "summary": build_claim_paper_evidence_map_summary(result),
  }
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
