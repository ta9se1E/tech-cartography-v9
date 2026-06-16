#!/usr/bin/env python3
"""Run Top5 controlled full text evidence collection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.reports.fulltext_evidence_export import save_controlled_fulltext_outputs
from tech_cartography.reports.fulltext_evidence_report import (
  build_fulltext_evidence_summary,
  render_fulltext_evidence_markdown,
)
from tech_cartography.reports.project_export import load_records_csv
from tech_cartography.retrieval.patent_fulltext_retriever import (
  FullTextRetrievalConfig,
  retrieve_controlled_fulltext_run,
)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Collect Top5 controlled full text evidence")
  parser.add_argument("--input-csv", required=True)
  parser.add_argument("--strategic-watch-csv", default=None)
  parser.add_argument("--output-dir", default="outputs/top5_fulltext_collection")
  parser.add_argument("--cache-dir", default="data/runtime/fulltext_cache")
  parser.add_argument("--maximum-gb", type=float, default=50.0)
  parser.add_argument("--project-id", default=None)
  parser.add_argument("--execute", action="store_true", default=False)
  parser.add_argument("--execute-limit", type=int, default=1)
  parser.add_argument("--publication-number", default=None)
  parser.add_argument("--confirm-fulltext-execute", action="store_true", default=False)
  parser.add_argument("--fulltext-scope", default="claims_only", choices=["claims_only", "description_only", "claims_and_description"])
  parser.add_argument("--maximum-fulltext-usd", type=float, default=10.0)
  parser.add_argument("--allow-expensive-fulltext", action="store_true", default=False)
  parser.add_argument("--preview-only", action="store_true", default=False)
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
  strategic_watch = []
  if args.strategic_watch_csv and Path(args.strategic_watch_csv).exists():
    strategic_watch = load_records_csv(args.strategic_watch_csv)

  config = FullTextRetrievalConfig(
    project_id=args.project_id,
    dry_run=not args.execute,
    execute=bool(args.execute),
    maximum_bytes_billed_gb=args.maximum_gb,
    output_dir=args.output_dir,
    cache_dir=args.cache_dir,
    use_cache=not args.no_cache,
    execute_limit=int(args.execute_limit),
    publication_number=args.publication_number,
    confirm_fulltext_execute=bool(args.confirm_fulltext_execute),
    preview_only=bool(args.preview_only),
    fulltext_scope=args.fulltext_scope,
    maximum_fulltext_usd=float(args.maximum_fulltext_usd),
    allow_expensive_fulltext=bool(args.allow_expensive_fulltext),
  )
  result = retrieve_controlled_fulltext_run(
    candidates,
    config,
    strategic_watch_candidates=strategic_watch,
  )
  summary = build_fulltext_evidence_summary(result)
  markdown = render_fulltext_evidence_markdown(summary)
  paths = save_controlled_fulltext_outputs(
    config.output_dir,
    plan=result.get("plan", {}),
    result={**result, "summary": summary},
    markdown=markdown,
    checklist_md=result.get("checklist_markdown", ""),
    use_timestamp_subdir=True,
  )
  payload = {"result": result, "summary": summary, "paths": paths}
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
  raise SystemExit(main())
