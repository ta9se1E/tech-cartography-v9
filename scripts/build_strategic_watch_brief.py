#!/usr/bin/env python3
"""Build Strategic Watch Brief from existing outputs (Phase 23.5)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.strategic_watch.brief_builder import (
  build_strategic_watch_brief,
  dry_run_strategic_watch_brief,
)
from tech_cartography.strategic_watch.store import save_strategic_watch_brief


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Build Strategic Watch Brief")
  parser.add_argument("--publication-number", required=True)
  parser.add_argument(
    "--web-signal-link-dir",
    default=None,
    help="Directory with web_signal_link_candidates.csv",
  )
  parser.add_argument("--output-dir", default=None)
  parser.add_argument("--min-watch-score", type=int, default=40)
  parser.add_argument("--top-n", type=int, default=10)
  parser.add_argument("--dry-run", action="store_true", default=False)
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  pub = str(args.publication_number).strip()
  output_dir = args.output_dir or f"outputs/strategic_watch_briefs/{pub}"

  if args.dry_run:
    result = dry_run_strategic_watch_brief(
      publication_number=pub,
      project_root=PROJECT_ROOT,
      web_signal_link_dir=args.web_signal_link_dir,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0

  brief = build_strategic_watch_brief(
    publication_number=pub,
    project_root=PROJECT_ROOT,
    web_signal_link_dir=args.web_signal_link_dir,
    min_watch_score=args.min_watch_score,
    top_n=args.top_n,
  )
  paths = save_strategic_watch_brief(brief, PROJECT_ROOT / output_dir)
  high = sum(1 for item in brief.watch_items if item.watch_priority == "high")
  medium = sum(1 for item in brief.watch_items if item.watch_priority == "medium")
  low = sum(1 for item in brief.watch_items if item.watch_priority == "low")
  print(
    json.dumps(
      {
        "publication_number": brief.publication_number,
        "watch_item_count": len(brief.watch_items),
        "top_watch_item_count": len(brief.top_watch_items),
        "high_priority_count": high,
        "medium_priority_count": medium,
        "low_priority_count": low,
        "output_dir": str(PROJECT_ROOT / output_dir),
        "paths": {key: str(path) for key, path in paths.items()},
      },
      indent=2,
      ensure_ascii=False,
    ),
  )
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
