"""CLI entrypoint for the thin v9 Cloud Run weekly job adapter."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.cloud_weekly_job import run_cloud_weekly_job  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description="Run Tech Cartography v9 Cloud weekly delivery job.")
  parser.add_argument("--output-root", default="", help="Override persistence root.")
  return parser


def main(argv: list[str] | None = None) -> int:
  args = build_parser().parse_args(argv)
  output_root = Path(args.output_root).resolve() if str(args.output_root or "").strip() else None
  result = run_cloud_weekly_job(output_root=output_root)
  print(json.dumps(result, ensure_ascii=False, indent=2))
  status = str(result.get("status", "failed") or "failed")
  if status in {"success", "partial_success", "skipped"}:
    return 0
  if status == "blocked":
    return 2
  return 1


if __name__ == "__main__":
  raise SystemExit(main())
