#!/usr/bin/env python3
"""Plan/apply helper to reset study demo active data from seed."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from services_v9.study_demo_config import STUDY_DEMO_BUCKET_DEFAULT, get_study_demo_bucket
from services_v9.study_demo_storage import ACTIVE_PREFIX, SEED_PREFIX, reset_history_object_path


def build_plan(*, demo_bucket: str) -> dict[str, Any]:
  return {
    "status": "plan",
    "demo_bucket": demo_bucket,
    "source_prefix": SEED_PREFIX,
    "target_prefix": ACTIVE_PREFIX,
    "history_prefix": reset_history_object_path(""),
    "actions": [
      "copy seed/* to active/*",
      "write reset record under reset_history/",
    ],
    "forbidden": [
      "production bucket access",
      "delete seed/*",
      "UI-triggered reset",
    ],
    "apply_guard": "V9_STUDY_DEMO_RESET_APPROVED=true",
  }


def main() -> int:
  parser = argparse.ArgumentParser(description="Reset study demo active data from seed")
  parser.add_argument("--plan", action="store_true", default=True)
  parser.add_argument("--apply", action="store_true")
  parser.add_argument("--demo-bucket", default="")
  args = parser.parse_args()
  demo_bucket = str(args.demo_bucket or get_study_demo_bucket() or STUDY_DEMO_BUCKET_DEFAULT).strip()
  plan = build_plan(demo_bucket=demo_bucket)

  if args.apply:
    if os.environ.get("V9_STUDY_DEMO_RESET_APPROVED", "").lower() != "true":
      print("ERROR: --apply requires V9_STUDY_DEMO_RESET_APPROVED=true", file=sys.stderr)
      return 1
    from services_v9.study_demo_gcs import default_storage_client, reset_active_from_seed

    result = reset_active_from_seed(default_storage_client(), demo_bucket=demo_bucket)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "reset" else 1

  print(json.dumps(plan, ensure_ascii=False, indent=2))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
