#!/usr/bin/env python3
"""Install or generate local weekly digest scheduler files (Phase 24.3)."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.delivery.scheduler_config import (
  SchedulerConfig,
  save_scheduler_bundle,
)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Generate/install weekly digest scheduler files")
  parser.add_argument("--publication-number", required=True)
  parser.add_argument("--recipient-config", required=True)
  parser.add_argument("--recipient-group", default="default")
  parser.add_argument("--output-dir", default="outputs/delivery")
  parser.add_argument("--project-dir", default=str(PROJECT_ROOT))
  parser.add_argument("--python-bin", default=sys.executable)
  parser.add_argument("--weekday", type=int, default=1)
  parser.add_argument("--hour", type=int, default=8)
  parser.add_argument("--minute", type=int, default=30)
  parser.add_argument("--timezone", default="Asia/Tokyo")
  parser.add_argument("--enable-send", action="store_true", default=False)
  parser.add_argument("--install", action="store_true", default=False)
  parser.add_argument("--yes", action="store_true", default=False)
  parser.add_argument("--label", default="com.techcartography.weeklydigest")
  parser.add_argument("--allow-repeat-this-week", action="store_true", default=False)
  parser.add_argument("--include-zip", action=argparse.BooleanOptionalAction, default=True)
  return parser.parse_args()


def install_launchd_agent(plist_path: Path, label: str) -> tuple[bool, str]:
  agents_dir = Path.home() / "Library" / "LaunchAgents"
  agents_dir.mkdir(parents=True, exist_ok=True)
  dest = agents_dir / f"{label}.plist"

  try:
    if dest.exists():
      unload = subprocess.run(
        ["launchctl", "unload", str(dest)],
        capture_output=True,
        text=True,
        check=False,
      )
      if unload.returncode != 0 and unload.stderr.strip():
        return False, f"launchctl unload failed: {unload.stderr.strip()}"

    shutil.copy2(plist_path, dest)
    load = subprocess.run(
      ["launchctl", "load", str(dest)],
      capture_output=True,
      text=True,
      check=False,
    )
    if load.returncode != 0:
      return False, f"launchctl load failed: {load.stderr.strip() or load.stdout.strip()}"
    return True, f"launchctl load succeeded: {dest}"
  except OSError as exc:
    return False, f"launchctl install failed: {exc}"


def main() -> int:
  args = parse_args()
  project_dir = Path(args.project_dir).resolve()
  config = SchedulerConfig(
    project_dir=project_dir,
    python_bin=Path(args.python_bin),
    publication_number=str(args.publication_number).strip(),
    recipient_config=str(args.recipient_config),
    recipient_group=str(args.recipient_group).strip(),
    output_dir=str(args.output_dir),
    weekday=args.weekday,
    hour=args.hour,
    minute=args.minute,
    timezone=args.timezone,
    enable_send=args.enable_send,
    label=str(args.label).strip(),
    allow_repeat_this_week=args.allow_repeat_this_week,
    include_zip=args.include_zip,
  )

  paths = save_scheduler_bundle(config)
  payload: dict[str, object] = {
    "publication_number": config.publication_number,
    "recipient_group": config.recipient_group,
    "enable_send": config.enable_send,
    "install_requested": args.install,
    "yes": args.yes,
    "paths": {key: str(path) for key, path in paths.items()},
  }

  install_message = "launchctl not run (--install and --yes required)"
  if args.install:
    if not args.yes:
      install_message = "launchctl not run: --yes is required with --install"
    else:
      ok, install_message = install_launchd_agent(paths["launchd_plist"], config.label)
      payload["install_ok"] = ok
  payload["install_message"] = install_message

  print(json.dumps(payload, indent=2, ensure_ascii=False))
  if args.install and args.yes and not payload.get("install_ok", False):
    return 1
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
