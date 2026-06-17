#!/usr/bin/env python3
"""Diagnose BigQuery fulltext availability for a US publication (Phase 18A)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.retrieval.bigquery_fulltext_availability_probe import (
  execute_availability_probe,
  probe_result_to_public_dict,
  save_availability_probe_result,
)
from tech_cartography.retrieval.publication_number_variants import build_publication_number_variants


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Check BigQuery fulltext availability for one publication")
  parser.add_argument("--publication-number", required=True)
  parser.add_argument("--scope", default="claims_only", choices=["claims_only", "description_only", "claims_and_description"])
  parser.add_argument("--run-dir", default="", help="Pipeline run directory for probe output")
  parser.add_argument("--execute", action="store_true", default=False, help="Execute probe query (default: dry-run classify only)")
  parser.add_argument("--max-probe-usd", type=float, default=2.0)
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  output_dir = args.run_dir or str(PROJECT_ROOT / "outputs" / "fulltext_availability_checks")
  out_path = Path(output_dir)
  out_path.mkdir(parents=True, exist_ok=True)

  variants = build_publication_number_variants(args.publication_number)
  result = execute_availability_probe(
    args.publication_number,
    scope=args.scope,
    variants=variants,
    execute=bool(args.execute),
    max_probe_usd=float(args.max_probe_usd),
  )
  paths = save_availability_probe_result(result, out_path)
  public = probe_result_to_public_dict(result)
  payload = {
    "publication_number": args.publication_number,
    "scope": args.scope,
    "variants_checked": variants,
    "probe_status": result.probe_status,
    "user_status_japanese": result.user_status_japanese,
    "next_action_japanese": result.next_action_japanese,
    "output_paths": paths,
    "public_summary": public,
  }
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
