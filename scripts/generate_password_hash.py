#!/usr/bin/env python3
"""Generate bcrypt password hashes for TECH_CARTOGRAPHY_USERS_JSON."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from tech_cartography.auth.basic_auth import hash_password  # noqa: E402


def main() -> int:
  parser = argparse.ArgumentParser(description="Generate bcrypt hash for basic auth users JSON.")
  parser.add_argument(
    "--password",
    help="Password to hash (omit to read interactively; input is hidden).",
  )
  args = parser.parse_args()
  if args.password is not None:
    password = args.password
  else:
    password = getpass.getpass("Password: ")
  if not password:
    print("Error: empty password", file=sys.stderr)
    return 1
  print(hash_password(password))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
