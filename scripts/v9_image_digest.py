"""Normalize and compare container image digests for deploy verification."""

from __future__ import annotations

import re
import sys

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_DIGEST_TOKEN_RE = re.compile(r"sha256:([0-9a-fA-F]{64})")


def normalize_digest(value: str | None) -> str:
  """Return canonical ``sha256:<64 lowercase hex>`` or raise ValueError."""
  if value is None:
    raise ValueError("digest is empty")
  raw = str(value).strip()
  if not raw:
    raise ValueError("digest is empty")

  if "@" in raw:
    raw = raw.rsplit("@", 1)[-1]

  match = _DIGEST_TOKEN_RE.search(raw)
  if match:
    hex_part = match.group(1).lower()
  else:
    hex_part = raw.lower()
    if hex_part.startswith("sha256:"):
      hex_part = hex_part.split(":", 1)[1]

  if not _SHA256_HEX_RE.fullmatch(hex_part):
    raise ValueError(f"invalid digest format: {value!r}")

  return f"sha256:{hex_part}"


def digests_match(expected: str | None, actual: str | None) -> bool:
  try:
    return normalize_digest(expected) == normalize_digest(actual)
  except ValueError:
    return False


def extract_build_image_digest(build_payload: dict) -> str:
  images = build_payload.get("results", {}).get("images", []) or []
  for item in images:
    if isinstance(item, dict) and item.get("digest"):
      return normalize_digest(str(item["digest"]))
  raise ValueError("Cloud Build results.images digest missing")


def main() -> int:
  if len(sys.argv) < 2:
    print("usage: v9_image_digest.py normalize <value>", file=sys.stderr)
    return 2
  command = sys.argv[1]
  if command == "normalize":
    if len(sys.argv) != 3:
      print("usage: v9_image_digest.py normalize <value>", file=sys.stderr)
      return 2
    try:
      print(normalize_digest(sys.argv[2]))
      return 0
    except ValueError as exc:
      print(str(exc), file=sys.stderr)
      return 1
  print(f"unknown command: {command}", file=sys.stderr)
  return 2


if __name__ == "__main__":
  sys.exit(main())
