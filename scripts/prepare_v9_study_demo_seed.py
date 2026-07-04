#!/usr/bin/env python3
"""Plan/apply helper to copy sanitized production artifacts into the study demo bucket."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from services_v9.study_demo_config import (
  PRODUCTION_PERSIST_BUCKET,
  SOURCE_RUN_ID_DEFAULT,
  STUDY_DEMO_BUCKET_DEFAULT,
  get_study_demo_bucket,
)
from services_v9.study_demo_storage import (
  EXCLUDED_COPY_NAMES,
  SEED_COPY_ALLOWLIST,
  SEED_MANIFEST_NAME,
  SEED_ROOT_ALLOWLIST,
  build_seed_manifest,
  production_weekly_run_prefix,
  seed_object_path,
)


def build_plan(*, source_run_id: str, demo_bucket: str) -> dict[str, Any]:
  run_prefix = production_weekly_run_prefix(source_run_id)
  copied = [seed_object_path(f"{run_prefix}{name}") for name in SEED_COPY_ALLOWLIST]
  copied.append(seed_object_path("watch_profile_current.json"))
  copied.append(seed_object_path("v9_config/weekly_delivery_config.json"))
  copied.append(seed_object_path(SEED_MANIFEST_NAME))
  excluded = [
    seed_object_path(f"{run_prefix}{name}") for name in EXCLUDED_COPY_NAMES
  ] + [
    "email_delivery_runs/**",
    "weekly_locks/**",
    "cloud_job_locks/**",
  ]
  return {
    "status": "plan",
    "source_bucket": PRODUCTION_PERSIST_BUCKET,
    "source_run_id": source_run_id,
    "source_prefix": run_prefix,
    "demo_bucket": demo_bucket,
    "seed_prefix": "seed/",
    "active_prefix": "active/",
    "copy_allowlist": list(SEED_COPY_ALLOWLIST) + list(SEED_ROOT_ALLOWLIST) + ["v9_config/weekly_delivery_config.json"],
    "planned_seed_objects": copied,
    "excluded": excluded,
    "labels": {
      "source_type": "production_copy",
      "copied_for": "study_demo",
      "external_retrieval_enabled": False,
    },
    "apply_guard": "V9_STUDY_DEMO_DATA_COPY_APPROVED=true",
    "notes": [
      "production bucket is read-only",
      "recipient/email/secret fields are stripped during copy",
      "Stage A does not execute --apply",
    ],
  }


def main() -> int:
  parser = argparse.ArgumentParser(description="Prepare study demo seed data")
  parser.add_argument("--plan", action="store_true", default=True)
  parser.add_argument("--apply", action="store_true")
  parser.add_argument("--source-run-id", default=SOURCE_RUN_ID_DEFAULT)
  parser.add_argument("--demo-bucket", default="")
  args = parser.parse_args()
  demo_bucket = str(args.demo_bucket or get_study_demo_bucket() or STUDY_DEMO_BUCKET_DEFAULT).strip()

  if args.apply:
    if os.environ.get("V9_STUDY_DEMO_DATA_COPY_APPROVED", "").lower() != "true":
      print("ERROR: --apply requires V9_STUDY_DEMO_DATA_COPY_APPROVED=true", file=sys.stderr)
      return 1
    manifest = build_seed_manifest(
      source_run_id=args.source_run_id,
      copied_objects=[item for item in build_plan(source_run_id=args.source_run_id, demo_bucket=demo_bucket)["planned_seed_objects"]],
      excluded_objects=build_plan(source_run_id=args.source_run_id, demo_bucket=demo_bucket)["excluded"],
    )
    print(json.dumps({"status": "blocked_in_stage_a", "manifest_preview_keys": list(manifest.keys())}, indent=2))
    return 0

  print(json.dumps(build_plan(source_run_id=args.source_run_id, demo_bucket=demo_bucket), ensure_ascii=False, indent=2))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
