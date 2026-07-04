#!/usr/bin/env python3
"""Plan/apply helper for the isolated v9 study demo shared password secret."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from typing import Any

from services_v9.study_demo_auth import validate_password_length
from services_v9.study_demo_config import (
  STUDY_DEMO_PASSWORD_SECRET,
  STUDY_DEMO_PROJECT_DEFAULT,
  STUDY_DEMO_SERVICE_ACCOUNT,
)


def build_plan() -> dict[str, Any]:
  return {
    "status": "plan",
    "secret_name": STUDY_DEMO_PASSWORD_SECRET,
    "project_id": STUDY_DEMO_PROJECT_DEFAULT,
    "service_account": STUDY_DEMO_SERVICE_ACCOUNT,
    "actions": [
      "create secret container if missing",
      "add new secret version from getpass input (not CLI args)",
      "grant roles/secretmanager.secretAccessor to study demo service account only",
    ],
    "forbidden_grants": [
      "production service account",
      "production job service account",
      "scheduler service account",
    ],
    "apply_guard": "V9_STUDY_DEMO_PASSWORD_APPROVED=true",
    "password_rules": {
      "minimum_length": 16,
      "no_whitespace_only": True,
      "no_cli_args": True,
      "no_stdout": True,
      "no_file_write": True,
    },
  }


def prompt_password_twice() -> str:
  first = getpass.getpass("Study demo password: ")
  second = getpass.getpass("Confirm study demo password: ")
  if first != second:
    raise SystemExit("ERROR: password confirmation did not match")
  if not validate_password_length(first):
    raise SystemExit("ERROR: password must be at least 16 non-whitespace characters")
  return first


def main() -> int:
  parser = argparse.ArgumentParser(description="Create study demo password secret version")
  parser.add_argument("--plan", action="store_true", default=True, help="Show plan only (default)")
  parser.add_argument("--apply", action="store_true", help="Create secret version (requires approval guard)")
  args = parser.parse_args()
  mode = "apply" if args.apply else "plan"

  if mode == "plan":
    print(json.dumps(build_plan(), ensure_ascii=False, indent=2))
    return 0

  import os

  if os.environ.get("V9_STUDY_DEMO_PASSWORD_APPROVED", "").lower() != "true":
    print("ERROR: --apply requires V9_STUDY_DEMO_PASSWORD_APPROVED=true", file=sys.stderr)
    return 1

  _ = prompt_password_twice()
  print(
    json.dumps(
      {
        "status": "blocked_in_stage_a",
        "message": "Stage A does not apply secret changes. Run Stage B with gcloud after local approval.",
        "secret_name": STUDY_DEMO_PASSWORD_SECRET,
      },
      ensure_ascii=False,
      indent=2,
    )
  )
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
