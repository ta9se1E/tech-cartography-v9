#!/usr/bin/env python3
"""Build Patent × Paper × Web Signal link candidates (Phase 23.4 / 23.4.1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.web_signals.linker import (
  LinkScoringConfig,
  build_web_signal_link_pack,
  dry_run_link_build,
  is_high_priority_link,
  is_top_priority_link,
  is_weak_link_candidate,
  save_web_signal_link_pack,
)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Build Patent × Paper × Web Signal link candidates")
  parser.add_argument("--publication-number", required=True)
  parser.add_argument("--evidence-map-dir", default=None)
  parser.add_argument("--openalex-dir", default=None)
  parser.add_argument(
    "--web-signal-review-dir",
    default="outputs/web_signals/tavily_pan_carbon_fiber/review_pack",
  )
  parser.add_argument("--output-dir", default=None)
  parser.add_argument("--min-link-score", type=int, default=40)
  parser.add_argument("--top-n", type=int, default=20)
  parser.add_argument("--include-ir-disclosure", action="store_true", default=True)
  parser.add_argument("--no-include-ir-disclosure", action="store_false", dest="include_ir_disclosure")
  parser.add_argument("--include-company-local-news", action="store_true", default=True)
  parser.add_argument(
    "--no-include-company-local-news",
    action="store_false",
    dest="include_company_local_news",
  )
  parser.add_argument("--calibrated-scoring", action="store_true", default=True)
  parser.add_argument("--no-calibrated-scoring", action="store_false", dest="calibrated_scoring")
  parser.add_argument("--min-high-priority-score", type=int, default=70)
  parser.add_argument("--min-top-priority-score", type=int, default=80)
  parser.add_argument("--exclude-broad-only-from-high-priority", action="store_true", default=True)
  parser.add_argument(
    "--no-exclude-broad-only-from-high-priority",
    action="store_false",
    dest="exclude_broad_only_from_high_priority",
  )
  parser.add_argument("--include-weak-links", action="store_true", default=True)
  parser.add_argument("--no-include-weak-links", action="store_false", dest="include_weak_links")
  parser.add_argument("--dry-run", action="store_true", default=False)
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  pub = str(args.publication_number).strip()
  output_dir = args.output_dir or f"outputs/web_signal_links/{pub}"
  scoring_config = LinkScoringConfig(
    calibrated_scoring=args.calibrated_scoring,
    min_high_priority_score=args.min_high_priority_score,
    min_top_priority_score=args.min_top_priority_score,
    exclude_broad_only_from_high_priority=args.exclude_broad_only_from_high_priority,
    include_weak_links=args.include_weak_links,
  )

  if args.dry_run:
    result = dry_run_link_build(
      publication_number=pub,
      project_root=PROJECT_ROOT,
      web_signal_review_dir=args.web_signal_review_dir,
      evidence_map_dir=args.evidence_map_dir,
      openalex_dir=args.openalex_dir,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0

  pack = build_web_signal_link_pack(
    publication_number=pub,
    project_root=PROJECT_ROOT,
    web_signal_review_dir=args.web_signal_review_dir,
    evidence_map_dir=args.evidence_map_dir,
    openalex_dir=args.openalex_dir,
    min_link_score=args.min_link_score,
    top_n=args.top_n,
    include_ir_disclosure=args.include_ir_disclosure,
    include_company_local_news=args.include_company_local_news,
    scoring_config=scoring_config,
  )
  paths = save_web_signal_link_pack(pack, PROJECT_ROOT / output_dir, scoring_config=scoring_config)
  print(
    json.dumps(
      {
        "publication_number": pack.publication_number,
        "link_candidate_count": len(pack.link_candidates),
        "top_priority_count": sum(1 for item in pack.link_candidates if is_top_priority_link(item, scoring_config)),
        "high_priority_count": sum(1 for item in pack.link_candidates if is_high_priority_link(item, scoring_config)),
        "weak_count": sum(1 for item in pack.link_candidates if is_weak_link_candidate(item)),
        "calibrated_scoring": scoring_config.calibrated_scoring,
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
