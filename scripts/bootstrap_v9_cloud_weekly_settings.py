"""Bootstrap the cloud weekly delivery settings with enabled=false."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.cloud_weekly_settings import (  # noqa: E402
  load_weekly_delivery_settings,
  mask_email_address,
  resolve_allowed_recipients,
  save_weekly_delivery_settings,
)


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description="Bootstrap v9 cloud weekly delivery settings.")
  parser.add_argument("--recipient-email", default="", help="Recipient email for the disabled bootstrap config.")
  parser.add_argument("--weekday", default="MON")
  parser.add_argument("--hour", type=int, default=9)
  parser.add_argument("--minute", type=int, default=0)
  parser.add_argument("--timezone", default="Asia/Tokyo")
  parser.add_argument("--email-mode", default="self_only")
  return parser


def _pick_recipient(explicit_recipient: str) -> str:
  recipient = str(explicit_recipient or "").strip().lower()
  if recipient:
    return recipient
  allowed = list(resolve_allowed_recipients())
  return str(allowed[0] if allowed else "").strip().lower()


def main(argv: list[str] | None = None) -> int:
  args = build_parser().parse_args(argv)
  recipient = _pick_recipient(args.recipient_email)
  save_result = save_weekly_delivery_settings(
    {
      "enabled": False,
      "recipient_email": recipient,
      "weekday": str(args.weekday or "MON").strip().upper(),
      "hour": int(args.hour),
      "minute": int(args.minute),
      "timezone": str(args.timezone or "Asia/Tokyo").strip() or "Asia/Tokyo",
      "email_mode": str(args.email_mode or "self_only").strip().lower() or "self_only",
    },
    updated_by="cloud-bootstrap",
  )
  settings = dict(save_result.get("settings", {}) or {})
  loaded = load_weekly_delivery_settings()
  payload = {
    "status": "ok",
    "storage_mode": str(save_result.get("storage_mode", "") or ""),
    "location": str(save_result.get("location", "") or ""),
    "enabled": bool(loaded.get("enabled", False)),
    "revision": int(loaded.get("revision", 0) or 0),
    "updated_at": str(loaded.get("updated_at", "") or ""),
    "recipient_masked": mask_email_address(str(settings.get("recipient_email", "") or "")),
    "schema_version": str(loaded.get("schema_version", "") or ""),
  }
  print(json.dumps(payload, ensure_ascii=False, indent=2))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
