#!/usr/bin/env python3
"""Run Top5 full text evidence collection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.reports.fulltext_evidence_report import (
  build_fulltext_evidence_summary,
  render_fulltext_evidence_markdown,
)
from tech_cartography.reports.project_export import load_records_csv
from tech_cartography.retrieval.patent_fulltext_retriever import (
  FullTextRetrievalConfig,
  retrieve_fulltext_for_top_candidates,
  save_fulltext_collection_results,
)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Collect Top5 full text evidence")
  parser.add_argument("--input-csv", required=True)
  parser.add_argument("--output-dir", default="outputs/top5_fulltext_collection")
  parser.add_argument("--cache-dir", default="data/runtime/fulltext_cache")
  parser.add_argument("--maximum-gb", type=float, default=50.0)
  parser.add_argument("--project-id", default=None)
  parser.add_argument("--execute", action="store_true", default=False)
  parser.add_argument("--no-cache", action="store_true", default=False)
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  input_path = Path(args.input_csv)
  if not input_path.exists() and "latest" in str(input_path):
    parent = input_path.parent.parent
    candidates = sorted(parent.glob("*/top5_fulltext_candidates.csv"))
    if candidates:
      input_path = candidates[-1]

  candidates = load_records_csv(input_path)
  config = FullTextRetrievalConfig(
    project_id=args.project_id,
    dry_run=not args.execute,
    execute=bool(args.execute),
    maximum_bytes_billed_gb=args.maximum_gb,
    output_dir=args.output_dir,
    cache_dir=args.cache_dir,
    use_cache=not args.no_cache,
  )
  result = retrieve_fulltext_for_top_candidates(candidates, config)
  summary = build_fulltext_evidence_summary(result)
  markdown = render_fulltext_evidence_markdown(summary)
  paths = save_fulltext_collection_results(
    result.get("retrieved_records", []),
    config.output_dir,
    summary=result,
    manual_records=result.get("manual_required_records", []),
    markdown=markdown,
  )
  payload = {"result": result, "summary": summary, "paths": paths}
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
  raise SystemExit(main())
