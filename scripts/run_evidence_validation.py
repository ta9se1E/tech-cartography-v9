#!/usr/bin/env python3
"""Run evidence validation pipeline from fulltext collection outputs."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
  sys.path.insert(0, str(SRC))

from tech_cartography.reports.project_export import load_records_csv
from tech_cartography.validation.evidence_validation import run_evidence_validation


def _load_fulltext_records(path: Path) -> list[dict]:
  data = json.loads(path.read_text(encoding="utf-8"))
  if isinstance(data, list):
    return data
  return list(data.get("retrieved_records") or [])


def main() -> int:
  parser = argparse.ArgumentParser(description="Run Claim Element × OpenAlex evidence validation.")
  parser.add_argument(
    "--fulltext-records-json",
    required=True,
    help="Path to top5_fulltext_records.json",
  )
  parser.add_argument(
    "--manual-candidates-csv",
    default=None,
    help="Path to strategic_watch_manual_fulltext_required.csv",
  )
  parser.add_argument("--execute-openalex", action="store_true", help="Execute OpenAlex queries (default: plan-only)")
  parser.add_argument("--max-queries", type=int, default=20)
  parser.add_argument("--max-results-per-query", type=int, default=10)
  parser.add_argument("--no-cache", action="store_true")
  parser.add_argument("--output-dir", default=None)
  args = parser.parse_args()

  fulltext_path = Path(args.fulltext_records_json)
  if not fulltext_path.exists():
    print(f"Missing fulltext records: {fulltext_path}", file=sys.stderr)
    return 1

  manual_candidates: list[dict] = []
  if args.manual_candidates_csv:
    manual_path = Path(args.manual_candidates_csv)
    if manual_path.exists():
      manual_candidates = load_records_csv(manual_path)

  timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
  output_dir = args.output_dir or str(ROOT / "outputs" / "evidence_validation" / timestamp)

  result = run_evidence_validation(
    fulltext_records=_load_fulltext_records(fulltext_path),
    manual_candidates=manual_candidates,
    execute_openalex=bool(args.execute_openalex),
    openalex_max_queries=args.max_queries,
    openalex_max_results_per_query=args.max_results_per_query,
    use_cache=not args.no_cache,
    output_dir=output_dir,
  )

  print(f"status: {result.get('status')}")
  print(f"output_dir: {result.get('output_paths', {}).get('output_dir', output_dir)}")
  for key, path in sorted((result.get("output_paths") or {}).items()):
    print(f"  {key}: {path}")
  return 0 if result.get("status") != "failed" else 1


if __name__ == "__main__":
  raise SystemExit(main())
