"""CLI entrypoint for the v9 weekly signal watch scheduler."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.weekly_scheduler import load_weekly_run_config, run_weekly_watch  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description="Run Tech Cartography v9 weekly watch scheduler.")
  parser.add_argument("--config", required=True, help="Path to weekly run config JSON.")
  parser.add_argument("--dry-run", action="store_true", help="Force dry-run mode.")
  parser.add_argument("--no-email", action="store_true", help="Force email sending off.")
  parser.add_argument("--run-id", default="", help="Explicit weekly run id.")
  parser.add_argument("--output-root", default="", help="Override v9 runs root directory.")
  return parser


def main(argv: list[str] | None = None) -> int:
  args = build_parser().parse_args(argv)
  try:
    config = load_weekly_run_config(args.config)
    if args.dry_run:
      config.setdefault("execution", {})["dry_run"] = True
    if args.no_email:
      config["_no_email"] = True
      config.setdefault("email", {})["mode"] = "preview"
      config.setdefault("email", {})["self_send_enabled"] = False
    if args.run_id:
      config["_run_id"] = str(args.run_id).strip()
    output_root = Path(args.output_root).resolve() if str(args.output_root or "").strip() else None
    result = run_weekly_watch(config, output_root=output_root, provider_adapters=None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    status = str(result.get("status", "failed") or "failed")
    if status in {"success", "partial_success"}:
      return 0
    if status == "blocked":
      return 2
    return 1
  except Exception as exc:  # noqa: BLE001
    error_payload = {
      "status": "failed",
      "error_type": type(exc).__name__,
      "safe_error_message": str(exc),
    }
    print(json.dumps(error_payload, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
