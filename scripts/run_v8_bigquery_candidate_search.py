#!/usr/bin/env python3
"""BigQuery candidate search CLI (Phase 27Q.1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
  sys.path.insert(0, str(SRC))

from tech_cartography.runtime.v8_research_theme_schema import ResearchThemeProfile
from tech_cartography.services.v8_bigquery_runner import run_bigquery_candidate_search
from tech_cartography.services.v8_bigquery_safety import BigQuerySafetyConfig


def main() -> int:
  parser = argparse.ArgumentParser(description="BigQuery candidate search (admin)")
  parser.add_argument("--case-id", required=True)
  parser.add_argument("--theme-profile", required=True)
  parser.add_argument("--mode", choices=["generate_sql", "dry_run", "execute"], default="generate_sql")
  args = parser.parse_args()

  theme_path = Path(args.theme_profile)
  if not theme_path.exists():
    print(f"theme profile not found: {theme_path}", file=sys.stderr)
    return 1

  profile = ResearchThemeProfile.from_dict(json.loads(theme_path.read_text(encoding="utf-8")))
  profile.case_id = args.case_id

  try:
    manifest = run_bigquery_candidate_search(
      case_id=args.case_id,
      theme_profile=profile,
      mode=args.mode,
      project_root=PROJECT_ROOT,
    )
  except PermissionError as exc:
    print(f"blocked: {exc}", file=sys.stderr)
    return 1
  except ImportError as exc:
    print(f"error: {exc}", file=sys.stderr)
    return 1

  print(f"case_id: {args.case_id}")
  print(f"mode: {args.mode}")
  print(f"output_dir: {manifest.output_dir}")
  print(f"sql_path: {manifest.sql_path}")
  if manifest.dry_run_path:
    print(f"dry_run_report: {manifest.dry_run_path}")
  if manifest.large_candidate_csv_path:
    print(f"large_candidate_csv: {manifest.large_candidate_csv_path}")
  print(f"ENABLE_BIGQUERY_RUN: {BigQuerySafetyConfig.from_env().enable_bigquery_run}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
