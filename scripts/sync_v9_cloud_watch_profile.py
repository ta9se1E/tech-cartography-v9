#!/usr/bin/env python
"""Plan/apply sync for the v9 cloud watch profile."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.cloud_watch_profile_sync import (  # noqa: E402
  apply_cloud_watch_profile_sync,
  plan_cloud_watch_profile_sync,
)


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description="Sync the Tech Cartography v9 cloud watch profile.")
  parser.add_argument("--plan", action="store_true", help="Show a read-only sync plan (default).")
  parser.add_argument("--apply", action="store_true", help="Apply the sync after approval and signature checks.")
  parser.add_argument("--expected-current-signature", default="", help="Expected current cloud profile signature.")
  parser.add_argument("--expected-source-signature", default="", help="Expected local source profile signature.")
  return parser


def main(argv: list[str] | None = None) -> int:
  args = build_parser().parse_args(argv)
  if args.apply:
    result = apply_cloud_watch_profile_sync(
      expected_current_signature=str(args.expected_current_signature or "").strip(),
      expected_source_signature=str(args.expected_source_signature or "").strip(),
    )
  else:
    result = plan_cloud_watch_profile_sync()
  print(json.dumps(result, ensure_ascii=False, indent=2))
  status = str(result.get("status", "failed") or "failed")
  if status in {"ok", "success"}:
    return 0
  if status == "blocked":
    return 2
  return 1


if __name__ == "__main__":
  raise SystemExit(main())
