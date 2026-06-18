#!/usr/bin/env python3
"""Run reproducibility smoke diagnostics for Evidence Map pipeline (Phase 22)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.validation.reproducibility_smoke import (
  DEFAULT_PUBLICATION_NUMBERS,
  ReproducibilitySmokeConfig,
  run_reproducibility_smoke,
  save_reproducibility_outputs,
)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description="Diagnose Evidence Map pipeline reproducibility for additional patent candidates",
  )
  parser.add_argument(
    "--publication-numbers",
    nargs="+",
    default=list(DEFAULT_PUBLICATION_NUMBERS),
    help="Target publication numbers",
  )
  parser.add_argument(
    "--output-dir",
    default="outputs/reproducibility_smoke",
    help="Output directory for summary artifacts",
  )
  parser.add_argument("--max-patents", type=int, default=3)
  parser.add_argument("--skip-bigquery", action="store_true", default=False)
  parser.add_argument("--use-existing-manual-inputs", action="store_true", default=False)
  parser.add_argument("--build-query-plan-if-manual-exists", action="store_true", default=False)
  parser.add_argument("--execute-openalex", action="store_true", default=False)
  parser.add_argument("--plan-only-openalex", action="store_true", default=True)
  parser.add_argument("--no-plan-only-openalex", action="store_false", dest="plan_only_openalex")
  parser.add_argument("--dry-run", action="store_true", default=False)
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  output_dir = Path(args.output_dir)
  if not output_dir.is_absolute():
    output_dir = PROJECT_ROOT / output_dir

  config = ReproducibilitySmokeConfig(
    publication_numbers=list(args.publication_numbers),
    output_dir=output_dir,
    project_root=PROJECT_ROOT,
    max_patents=int(args.max_patents),
    skip_bigquery=bool(args.skip_bigquery),
    use_existing_manual_inputs=bool(args.use_existing_manual_inputs),
    build_query_plan_if_manual_exists=bool(args.build_query_plan_if_manual_exists),
    execute_openalex=bool(args.execute_openalex),
    plan_only_openalex=bool(args.plan_only_openalex),
    dry_run=bool(args.dry_run),
  )

  run = run_reproducibility_smoke(config)
  paths = save_reproducibility_outputs(run, output_dir)
  payload = {
    "dry_run": run.dry_run,
    "patent_count": len(run.patents),
    "statuses": {p.publication_number: p.status for p in run.patents},
    "output_paths": paths,
  }
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
