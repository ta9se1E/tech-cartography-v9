#!/usr/bin/env python3
"""Run Tavily Web Signal search plan / execution (Phase 23.1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.web_signals.tavily_runner import TavilyRunConfig, run_tavily_web_signal_pipeline


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Plan or execute Tavily Web Signal search")
  parser.add_argument("--topic", required=True)
  parser.add_argument(
    "--categories",
    nargs="+",
    default=["national_project", "money", "ir_disclosure", "company", "local_news"],
  )
  parser.add_argument("--languages", nargs="+", default=["ja", "en"])
  parser.add_argument("--max-queries", type=int, default=10)
  parser.add_argument("--max-results-per-query", type=int, default=5)
  parser.add_argument("--include-domains", nargs="*", default=[])
  parser.add_argument("--exclude-domains", nargs="*", default=[])
  parser.add_argument("--output-dir", default=None)
  parser.add_argument("--dry-run", action="store_true", default=False)
  parser.add_argument("--plan-only", action="store_true", default=False)
  parser.add_argument(
    "--execute-tavily",
    action="store_true",
    default=False,
    help="Execute Tavily Search/Extract (requires TAVILY_API_KEY)",
  )
  parser.add_argument("--extract-top-urls", action="store_true", default=False)
  parser.add_argument("--max-extract-urls", type=int, default=3)
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  plan_only = args.plan_only or not args.execute_tavily

  config = TavilyRunConfig(
    topic=args.topic,
    categories=list(args.categories),
    languages=list(args.languages),
    max_queries=args.max_queries,
    max_results_per_query=args.max_results_per_query,
    include_domains=list(args.include_domains or []),
    exclude_domains=list(args.exclude_domains or []),
    output_dir=args.output_dir,
    dry_run=args.dry_run,
    plan_only=plan_only,
    execute_tavily=args.execute_tavily,
    extract_top_urls=args.extract_top_urls,
    max_extract_urls=args.max_extract_urls,
  )

  result = run_tavily_web_signal_pipeline(config)
  print(json.dumps({k: v for k, v in result.items() if k != "queries"}, indent=2, ensure_ascii=False))

  if result.get("status") == "blocked_missing_api_key":
    return 2
  if result.get("errors"):
    return 1
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
