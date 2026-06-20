#!/usr/bin/env python3
"""Build Core Validation Pack before MVP freeze (Phase 24.4)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.validation.core_validation import build_core_validation_summary
from tech_cartography.validation.store import save_core_validation_pack


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Build core validation pack")
  parser.add_argument(
    "--publication-numbers",
    nargs="+",
    default=["US-12565719-B2", "US-12435451-B2", "US-12516451-B2"],
  )
  parser.add_argument("--output-dir", default="outputs/validation/core_validation")
  parser.add_argument("--project-root", default=str(PROJECT_ROOT))
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  root = Path(args.project_root)
  out = Path(args.output_dir)
  if not out.is_absolute():
    out = root / out

  summary = build_core_validation_summary(root, args.publication_numbers)
  paths = save_core_validation_pack(summary, out)

  payload = {
    "output_dir": str(out),
    "publication_numbers": summary.publication_numbers,
    "complete_count": summary.complete_count,
    "blocked_manual_claims_count": summary.blocked_manual_claims_count,
    "freeze_recommendation": summary.freeze_recommendation,
    "paths": {key: str(path) for key, path in paths.items()},
  }
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
