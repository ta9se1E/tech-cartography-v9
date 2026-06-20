#!/usr/bin/env python3
"""Build cross-theme core validation summary for MVP freeze (Phase 24.4B)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.validation.core_validation_summary import (
  build_core_validation_summary,
  save_core_validation_summary_pack,
)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Build cross-theme core validation summary")
  parser.add_argument("--theme-id", required=True)
  parser.add_argument("--theme-name", required=True)
  parser.add_argument("--seed-publications", nargs="+", required=True)
  parser.add_argument("--output-dir", default="outputs/validation/core_validation")
  parser.add_argument("--project-root", default=str(PROJECT_ROOT))
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  root = Path(args.project_root)
  out = Path(args.output_dir)
  if not out.is_absolute():
    out = root / out

  summary = build_core_validation_summary(
    project_root=root,
    theme_id=args.theme_id,
    theme_name=args.theme_name,
    seed_publications=args.seed_publications,
  )
  paths = save_core_validation_summary_pack(summary, out)

  payload = {
    "output_dir": str(out),
    "theme_id": summary.theme_id,
    "theme_name": summary.theme_name,
    "seed_count": summary.seed_count,
    "stage2_pass_count": summary.stage2_pass_count,
    "stage3_pass_count": summary.stage3_pass_count,
    "freeze_readiness": summary.freeze_readiness,
    "paths": {key: str(path) for key, path in paths.items()},
  }
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
