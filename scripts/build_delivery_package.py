#!/usr/bin/env python3
"""Build Intelligence Delivery package — overview, report, digest, email draft (Phase 24.1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.delivery.japanese_copy import ja_status_description, ja_status_label, ja_status_message
from tech_cartography.delivery.store import build_delivery_package, dry_run_delivery_package


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Build Intelligence Delivery package")
  parser.add_argument("--publication-number", required=True)
  parser.add_argument("--output-dir", default="outputs/delivery")
  parser.add_argument("--previous-snapshot", default=None)
  parser.add_argument("--include-zip", action="store_true", default=True)
  parser.add_argument("--no-include-zip", action="store_false", dest="include_zip")
  parser.add_argument("--dry-run", action="store_true", default=False)
  parser.add_argument("--build-email-draft", action="store_true", default=False)
  parser.add_argument("--send-email", action="store_true", default=False)
  parser.add_argument("--email-to", default=None, help="Comma-separated recipient emails")
  parser.add_argument("--email-cc", default=None, help="Comma-separated CC emails")
  parser.add_argument("--subject-prefix", default=None)
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  pub = str(args.publication_number).strip()

  if args.dry_run:
    result = dry_run_delivery_package(pub, PROJECT_ROOT, args.output_dir)
    if args.build_email_draft:
      result["email_draft_planned"] = True
      result["send_email_requested"] = bool(args.send_email)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0

  result = build_delivery_package(
    publication_number=pub,
    project_root=PROJECT_ROOT,
    output_dir=args.output_dir,
    previous_snapshot_path=args.previous_snapshot,
    include_zip=args.include_zip,
    build_email_draft=args.build_email_draft,
    email_to=args.email_to,
    email_cc=args.email_cc,
    subject_prefix=args.subject_prefix,
    send_email=args.send_email,
  )

  payload: dict[str, object] = {
    "publication_number": result.publication_number,
    "output_dir": result.output_dir,
    "is_initial_digest": result.is_initial_digest,
    "snapshot_id": result.snapshot.snapshot_id if result.snapshot else None,
    "paths": {key: str(path) for key, path in result.paths.items()},
  }
  if result.email_draft:
    payload["email_draft"] = {
      "draft_id": result.email_draft.draft_id,
      "status": result.email_draft.status,
      "status_label": ja_status_label(result.email_draft.status),
      "message": ja_status_message(result.email_draft.status),
      "human_readable_summary": ja_status_description(result.email_draft.status),
      "to": result.email_draft.to,
      "subject": result.email_draft.subject,
    }
  if result.email_send_result:
    payload["email_send_result"] = result.email_send_result

  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
