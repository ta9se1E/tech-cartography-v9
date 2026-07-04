"""CLI entrypoint for the thin v9 Cloud Run weekly job adapter."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.cloud_weekly_job import (  # noqa: E402
  build_cloud_weekly_run_config,
  run_cloud_weekly_job,
  summarize_cloud_weekly_job_config,
)
from services_v9.cloud_runtime import get_persist_root  # noqa: E402
from services_v9.cloud_weekly_settings import load_weekly_delivery_settings  # noqa: E402

CONTROLLED_ZERO_EXIT_BLOCK_REASONS = {
  "approved_query_validation",
  "blocked_cost_guard",
  "blocked_execution_cap",
}


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description="Run Tech Cartography v9 Cloud weekly delivery job.")
  parser.add_argument("--output-root", default="", help="Override persistence root.")
  parser.add_argument("--print-config-summary", action="store_true", help="Print the resolved cloud job config summary without running the job.")
  return parser


def main(argv: list[str] | None = None) -> int:
  args = build_parser().parse_args(argv)
  output_root = Path(args.output_root).resolve() if str(args.output_root or "").strip() else None
  if args.print_config_summary:
    persist_root = output_root or get_persist_root()
    settings = load_weekly_delivery_settings(base_dir=persist_root)
    config = build_cloud_weekly_run_config(settings, persist_root=persist_root)
    print(json.dumps(summarize_cloud_weekly_job_config(config), ensure_ascii=False, indent=2))
    return 0
  result = run_cloud_weekly_job(output_root=output_root)
  print(json.dumps(result, ensure_ascii=False, indent=2))
  status = str(result.get("status", "failed") or "failed")
  if status in {"success", "partial_success", "skipped"}:
    return 0
  if status == "blocked":
    block_reason = str(result.get("block_reason", "") or "").strip()
    if bool(result.get("controlled_outcome", False)) and block_reason in CONTROLLED_ZERO_EXIT_BLOCK_REASONS:
      return 0
    return 2
  return 1


if __name__ == "__main__":
  raise SystemExit(main())
