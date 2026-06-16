#!/usr/bin/env python3
"""Run OpenAlex paper evidence search from claim element query candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.reports.paper_evidence_pipeline import (
  run_paper_evidence_pipeline,
  save_paper_evidence_outputs,
)
from tech_cartography.reports.paper_evidence_report import build_paper_evidence_summary
from tech_cartography.reports.project_export import build_output_directory, load_records_csv
from tech_cartography.retrieval.openalex_retriever import OpenAlexRetrievalConfig


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Run OpenAlex paper evidence search")
  parser.add_argument("--paper-query-csv", required=True)
  parser.add_argument("--claim-elements-csv", default="")
  parser.add_argument("--output-dir", default="outputs/openalex_paper_evidence")
  parser.add_argument("--cache-dir", default="data/runtime/openalex_cache")
  parser.add_argument("--max-queries", type=int, default=20)
  parser.add_argument("--max-results-per-query", type=int, default=10)
  parser.add_argument("--execute", action="store_true")
  parser.add_argument("--no-cache", action="store_true")
  parser.add_argument("--polite-email", default="")
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
  query_path = _resolve_latest(Path(args.paper_query_csv), "paper_query_candidates.csv")
  claim_path = (
    _resolve_latest(Path(args.claim_elements_csv), "claim_elements.csv")
    if args.claim_elements_csv
    else query_path.parent / "claim_elements.csv"
  )

  query_rows = load_records_csv(query_path) if query_path.exists() else []
  claim_elements = load_records_csv(claim_path) if claim_path.exists() else []

  config = OpenAlexRetrievalConfig(
    execute=args.execute,
    max_queries=args.max_queries,
    max_results_per_query=args.max_results_per_query,
    cache_dir=args.cache_dir,
    use_cache=not args.no_cache,
    polite_email=args.polite_email or None,
    output_dir=args.output_dir,
  )
  result = run_paper_evidence_pipeline(query_rows, claim_elements, config)
  output_dir = build_output_directory(args.output_dir)
  paths = save_paper_evidence_outputs(result, output_dir)
  payload = {
    "paper_query_csv": str(query_path),
    "claim_elements_csv": str(claim_path),
    "paths": paths,
    "summary": build_paper_evidence_summary(result),
  }
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
