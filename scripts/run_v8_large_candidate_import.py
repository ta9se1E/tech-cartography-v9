#!/usr/bin/env python3
"""Import large candidate CSV/Excel (Phase 27J.0)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
  sys.path.insert(0, str(SRC))

from tech_cartography.services.v8_large_candidate_import import import_large_candidates


def main() -> int:
  parser = argparse.ArgumentParser(description="Import large candidate file (max 1000 rows)")
  parser.add_argument("--case-id", required=True)
  parser.add_argument("--input", required=True)
  parser.add_argument("--max-rows", type=int, default=1000)
  parser.add_argument("--output-dir", default="")
  args = parser.parse_args()

  result = import_large_candidates(
    case_id=args.case_id,
    input_path=Path(args.input),
    max_rows=args.max_rows,
    project_root=PROJECT_ROOT,
  )
  print(f"case_id: {result.case_id}")
  print(f"input_row_count: {result.input_row_count}")
  print(f"accepted_row_count: {result.accepted_row_count}")
  print(f"rejected_row_count: {result.rejected_row_count}")
  print(f"output_candidates_path: {result.output_candidates_path}")
  print(f"output_profile_path: {result.output_profile_path}")
  for w in result.warnings:
    print(f"warning: {w}")
  return 0 if result.accepted_row_count > 0 else 1


if __name__ == "__main__":
  sys.exit(main())
