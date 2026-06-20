#!/usr/bin/env python3
"""Run weekly digest job for local scheduling (Phase 24.3)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.delivery.japanese_copy import ja_status_label
from tech_cartography.delivery.weekly_job import (
  build_weekly_job_config,
  run_weekly_digest_job,
)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Run weekly digest delivery job")
  parser.add_argument("--publication-number", required=True)
  parser.add_argument("--recipient-config", required=True)
  parser.add_argument("--recipient-group", default="default")
  parser.add_argument("--output-dir", default="outputs/delivery")
  parser.add_argument("--project-root", default=str(PROJECT_ROOT))
  parser.add_argument("--include-zip", action=argparse.BooleanOptionalAction, default=True)
  parser.add_argument("--build-draft", action=argparse.BooleanOptionalAction, default=True)
  parser.add_argument("--send-email", action="store_true", default=False)
  parser.add_argument("--dry-run", action="store_true", default=False)
  parser.add_argument("--timezone", default="Asia/Tokyo")
  parser.add_argument("--allow-repeat-this-week", action="store_true", default=False)
  parser.add_argument("--run-label", default="weekly_digest")
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  config_path = Path(args.recipient_config)
  if not config_path.is_absolute():
    config_path = Path(args.project_root) / config_path

  config = build_weekly_job_config(
    publication_number=str(args.publication_number).strip(),
    recipient_config_path=config_path,
    recipient_group=str(args.recipient_group).strip(),
    output_dir=args.output_dir,
    project_root=args.project_root,
    include_zip=args.include_zip,
    build_draft=args.build_draft,
    send_email=args.send_email,
    dry_run=args.dry_run,
    timezone=args.timezone,
    run_label=args.run_label,
    allow_repeat_this_week=args.allow_repeat_this_week,
  )

  result = run_weekly_digest_job(config)

  payload: dict[str, object] = result.to_dict()
  payload["status_label"] = ja_status_label(result.status) if result.status in {
    "dry_run", "draft_saved", "sent", "failed",
  } else result.status

  print(json.dumps(payload, indent=2, ensure_ascii=False))
  if result.status == "failed":
    return 1
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
