#!/usr/bin/env python3
"""Send weekly digest test email via explicit CLI (Phase 24.2)."""

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
from tech_cartography.delivery.weekly_digest_send import run_weekly_digest_send_test


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Send weekly digest test email (explicit CLI only)")
  parser.add_argument("--publication-number", required=True)
  parser.add_argument("--recipient-config", required=True)
  parser.add_argument("--recipient-group", default="default")
  parser.add_argument("--output-dir", default="outputs/delivery")
  parser.add_argument("--build-draft", action="store_true", default=False)
  parser.add_argument("--send-email", action="store_true", default=False)
  parser.add_argument("--dry-run", action="store_true", default=False)
  parser.add_argument("--subject-prefix", default=None)
  parser.add_argument("--include-zip", action="store_true", default=False)
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  config_path = Path(args.recipient_config)
  if not config_path.is_absolute():
    config_path = PROJECT_ROOT / config_path

  result = run_weekly_digest_send_test(
    publication_number=str(args.publication_number).strip(),
    project_root=PROJECT_ROOT,
    output_dir=args.output_dir,
    recipient_config_path=config_path,
    recipient_group=str(args.recipient_group).strip(),
    dry_run=args.dry_run,
    build_draft=args.build_draft,
    send_email=args.send_email,
    subject_prefix=args.subject_prefix,
    include_zip=args.include_zip,
  )

  payload: dict[str, object] = {
    "publication_number": result.publication_number,
    "output_dir": result.output_dir,
    "recipient_group": result.recipient_group,
    "to": result.to,
    "cc": result.cc,
    "dry_run": result.dry_run,
    "build_draft": result.build_draft,
    "send_email": result.send_email,
    "delivery_paths": result.delivery_paths,
  }
  if result.send_log:
    payload["send_log"] = {
      "log_id": result.send_log.log_id,
      "status": result.send_log.status,
      "status_label": ja_status_label(result.send_log.status),
      "message": result.send_log.message,
      "created_at": result.send_log.created_at,
      "to_count": result.send_log.to_count,
      "cc_count": result.send_log.cc_count,
    }
    payload["send_log_paths"] = {key: str(path) for key, path in result.send_log_paths.items()}
  if result.email_send_result:
    payload["email_send_result"] = result.email_send_result

  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
