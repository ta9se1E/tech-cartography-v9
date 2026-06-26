#!/usr/bin/env python3
"""Run staged shortlist Top100/Top20/Top5 (Phase 27J.0)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
  sys.path.insert(0, str(SRC))

from tech_cartography.services.v8_large_candidate_shortlist import build_staged_shortlist


def main() -> int:
  parser = argparse.ArgumentParser(description="Build Top100/Top20/Top5 staged shortlist")
  parser.add_argument("--case-id", required=True)
  parser.add_argument("--input", default="")
  parser.add_argument("--top100", type=int, default=100)
  parser.add_argument("--top20", type=int, default=20)
  parser.add_argument("--top5", type=int, default=5)
  args = parser.parse_args()

  input_path = Path(args.input) if args.input else None
  pack = build_staged_shortlist(
    args.case_id,
    input_path=input_path,
    top100=args.top100,
    top20=args.top20,
    top5=args.top5,
    project_root=PROJECT_ROOT,
  )
  sel = pack.selection
  print(f"case_id: {pack.case_id}")
  print(f"imported count: {sel.population_count}")
  print(f"deduped count: {sel.deduped_count}")
  print(f"top100 count: {sel.top100_count}")
  print(f"top20 count: {sel.top20_count}")
  print(f"top5 count: {sel.top5_count}")
  print(f"output_dir: {pack.output_dir}")
  print(f"manifest: {pack.manifest_path}")
  return 0 if sel.top5_count >= 1 or sel.deduped_count >= 1 else 1


if __name__ == "__main__":
  sys.exit(main())
