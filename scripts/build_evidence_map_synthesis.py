#!/usr/bin/env python3
"""Build Evidence Map synthesis report for a single patent (Phase 20)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.evidence.evidence_map_synthesizer import build_evidence_map_synthesis
from tech_cartography.reports.evidence_map_synthesis_report import save_evidence_map_synthesis_artifacts


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Build Evidence Map synthesis report")
  parser.add_argument("--publication-number", required=True)
  parser.add_argument("--run-dir", default="")
  parser.add_argument("--openalex-dir", default="")
  parser.add_argument("--output-dir", default="")
  parser.add_argument("--allow-weak-no-papers", action="store_true", default=True)
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  pub = str(args.publication_number).strip()
  output_dir = (
    Path(args.output_dir)
    if args.output_dir
    else Path("outputs/evidence_map_synthesis") / pub
  )
  synthesis = build_evidence_map_synthesis(
    args.run_dir or None,
    pub,
    args.openalex_dir or None,
    allow_weak_no_papers=bool(args.allow_weak_no_papers),
  )
  paths = save_evidence_map_synthesis_artifacts(synthesis, output_dir)
  payload = {
    "publication_number": pub,
    "synthesis_status": synthesis.synthesis_status,
    "claim_element_count": synthesis.claim_element_count,
    "selected_evidence_paper_count": synthesis.selected_evidence_paper_count,
    "claim_paper_link_count": synthesis.claim_paper_link_count,
    "paths": paths,
  }
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
