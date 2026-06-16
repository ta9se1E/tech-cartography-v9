#!/usr/bin/env python3
"""CLI for BigQuery light multi-query retrieval."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.config import load_carbon_fiber_demo_profile
from tech_cartography.retrieval.bigquery_light_retriever import (
  RetrievalConfig,
  run_multi_query_retrieval,
)
from tech_cartography.strategy.query_plan import QueryPlan
from tech_cartography.strategy.search_strategy_builder import build_search_strategy


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Run BigQuery light multi-query retrieval")
  parser.add_argument("--execute", action="store_true", default=False)
  parser.add_argument("--max-results-total", type=int, default=2000)
  parser.add_argument("--max-results-per-intent", type=int, default=500)
  parser.add_argument("--maximum-gb", type=float, default=300.0)
  parser.add_argument("--project-id", type=str, default=None)
  parser.add_argument(
    "--output-dir",
    type=str,
    default="outputs/bigquery_light_retrieval",
  )
  parser.add_argument("--no-cache", action="store_true", default=False)
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  profile = load_carbon_fiber_demo_profile()
  strategy = build_search_strategy(profile)
  query_plans = [QueryPlan.from_dict(item) for item in strategy["query_plans"]]

  config = RetrievalConfig(
    project_id=args.project_id,
    dry_run=not args.execute,
    execute=bool(args.execute),
    maximum_bytes_billed_gb=args.maximum_gb,
    max_results_per_intent=args.max_results_per_intent,
    max_results_total=args.max_results_total,
    output_dir=args.output_dir,
    use_cache=not args.no_cache,
  )

  result = run_multi_query_retrieval(query_plans, config)
  print(json.dumps(result, indent=2, ensure_ascii=False))
  return 0 if result.get("status") in {"ok", "cached"} else 1


if __name__ == "__main__":
  raise SystemExit(main())
