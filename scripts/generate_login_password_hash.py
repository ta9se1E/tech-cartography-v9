#!/usr/bin/env python3
"""Generate pbkdf2_sha256 password hashes for TECH_CARTOGRAPHY_USERS_JSON (Phase 25M)."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from tech_cartography.auth.basic_auth import hash_password_pbkdf2  # noqa: E402


def main() -> int:
  parser = argparse.ArgumentParser(description="Generate pbkdf2_sha256 password hash for multi-user login JSON.")
  parser.add_argument("--username", help="Username for sample JSON entry (optional)")
  parser.add_argument("--display-name", help="Display name for sample JSON entry")
  parser.add_argument("--role", default="member", choices=["member", "admin"], help="Role for sample JSON entry")
  parser.add_argument("--json", action="store_true", help="Print a sample TECH_CARTOGRAPHY_USERS_JSON entry")
  args = parser.parse_args()

  password = getpass.getpass("Password: ")
  confirm = getpass.getpass("Confirm password: ")
  if not password:
    print("Password must not be empty.", file=sys.stderr)
    return 1
  if password != confirm:
    print("Passwords do not match.", file=sys.stderr)
    return 1

  password_hash = hash_password_pbkdf2(password)
  if args.json:
    username = args.username or "member01"
    display_name = args.display_name or username
    entry = {
      "username": username,
      "display_name": display_name,
      "role": args.role,
      "password_hash": password_hash,
    }
    print(json.dumps([entry], ensure_ascii=False, indent=2))
  else:
    print(password_hash)
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
