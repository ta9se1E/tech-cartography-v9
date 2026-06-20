#!/usr/bin/env python3
"""Build Intelligence Delivery package — overview, report, digest, diff (Phase 24.0)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.delivery.store import build_delivery_package, dry_run_delivery_package


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Build Intelligence Delivery package")
  parser.add_argument("--publication-number", required=True)
  parser.add_argument("--output-dir", default="outputs/delivery")
  parser.add_argument("--previous-snapshot", default=None)
  parser.add_argument("--include-zip", action="store_true", default=True)
  parser.add_argument("--no-include-zip", action="store_false", dest="include_zip")
  parser.add_argument("--dry-run", action="store_true", default=False)
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  pub = str(args.publication_number).strip()

  if args.dry_run:
    result = dry_run_delivery_package(pub, PROJECT_ROOT, args.output_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0

  result = build_delivery_package(
    publication_number=pub,
    project_root=PROJECT_ROOT,
    output_dir=args.output_dir,
    previous_snapshot_path=args.previous_snapshot,
    include_zip=args.include_zip,
  )
  print(
    json.dumps(
      {
        "publication_number": result.publication_number,
        "output_dir": result.output_dir,
        "is_initial_digest": result.is_initial_digest,
        "snapshot_id": result.snapshot.snapshot_id if result.snapshot else None,
        "paths": {key: str(path) for key, path in result.paths.items()},
      },
      indent=2,
      ensure_ascii=False,
    ),
  )
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
