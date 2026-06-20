#!/usr/bin/env python3
"""Run cross-theme validation smoke (read-only by default) — Phase 24.4."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.validation.store import save_theme_validation_report
from tech_cartography.validation.theme_validation import (
  find_theme_case,
  load_theme_validation_config,
  run_theme_validation_smoke,
)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Theme validation smoke (no external API by default)")
  parser.add_argument("--theme-config", required=True)
  parser.add_argument("--theme-id", required=True)
  parser.add_argument("--publication-number", default=None)
  parser.add_argument("--manual-claims-path", default=None)
  parser.add_argument("--output-dir", default="outputs/validation/theme_validation")
  parser.add_argument("--project-root", default=str(PROJECT_ROOT))
  parser.add_argument("--dry-run", action="store_true", default=False)
  parser.add_argument("--seed-only", action="store_true", default=False)
  parser.set_defaults(no_external_api=True)
  parser.add_argument("--no-external-api", dest="no_external_api", action="store_true")
  parser.add_argument("--allow-external-api", dest="no_external_api", action="store_false")
  parser.add_argument("--max-patents", type=int, default=5)
  parser.add_argument("--max-papers", type=int, default=5)
  parser.add_argument("--max-web-signals", type=int, default=10)
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  root = Path(args.project_root)
  config_path = Path(args.theme_config)
  if not config_path.is_absolute():
    config_path = root / config_path

  cases = load_theme_validation_config(config_path)
  theme_case = find_theme_case(cases, args.theme_id)
  if theme_case is None:
    print(json.dumps({"error": f"theme_id not found: {args.theme_id}"}, ensure_ascii=False))
    return 1

  manual_path = None
  if args.manual_claims_path:
    manual_path = Path(args.manual_claims_path)
    if not manual_path.is_absolute():
      manual_path = root / manual_path

  result = run_theme_validation_smoke(
    project_root=root,
    theme_case=theme_case,
    publication_number=args.publication_number,
    manual_claims_path=manual_path,
    dry_run=args.dry_run,
    no_external_api=args.no_external_api,
    seed_only=args.seed_only,
  )

  out = Path(args.output_dir)
  if not out.is_absolute():
    out = root / out
  paths = save_theme_validation_report(result, out, project_root=root)

  payload = {
    "theme_id": result.theme_id,
    "overall_status": result.overall_status,
    "dry_run": result.dry_run,
    "no_external_api": result.no_external_api,
    "publication_number": result.publication_number,
    "limits": {
      "max_patents": args.max_patents,
      "max_papers": args.max_papers,
      "max_web_signals": args.max_web_signals,
    },
    "paths": {key: str(path) for key, path in paths.items()},
    "stages": [stage.to_dict() for stage in result.stages],
  }
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
