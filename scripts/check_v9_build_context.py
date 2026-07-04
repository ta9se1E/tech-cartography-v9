"""Verify the v9 Cloud Build upload set without reading file contents."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from scripts.v9_build_security import validate_upload_file_list  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description="Check the v9 Cloud Build upload file set.")
  parser.add_argument("--ignore-file", default=".gcloudignore", help="Ignore file passed to gcloud meta list-files-for-upload.")
  parser.add_argument("--minimum-count", type=int, default=20, help="Minimum expected upload file count.")
  return parser


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
  return subprocess.run(args, check=True, capture_output=True, text=True)


def resolve_listing_command(ignore_file: str) -> tuple[list[str], str]:
  help_text = _run(["gcloud", "meta", "list-files-for-upload", "--help"]).stdout
  if not Path(ignore_file).exists():
    raise RuntimeError(f"ignore file does not exist: {ignore_file}")
  if "--ignore-file" in help_text:
    return (["gcloud", "meta", "list-files-for-upload", f"--ignore-file={ignore_file}"], "explicit_ignore_file")
  if Path(ignore_file).name == ".gcloudignore":
    return (["gcloud", "meta", "list-files-for-upload", "."], "implicit_gcloudignore")
  raise RuntimeError("gcloud meta list-files-for-upload does not support --ignore-file for non-.gcloudignore paths.")


def list_files_for_upload(listing_command: list[str]) -> list[str]:
  completed = _run(listing_command)
  return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
  args = build_parser().parse_args(argv)
  try:
    listing_command, ignore_mode = resolve_listing_command(args.ignore_file)
    upload_files = list_files_for_upload(listing_command)
    validation = validate_upload_file_list(upload_files, minimum_count=max(args.minimum_count, 1))
  except Exception as exc:  # noqa: BLE001
    print(json.dumps({
      "status": "failed",
      "error": f"{type(exc).__name__}: {exc}",
    }, ensure_ascii=False, indent=2))
    return 1

  payload = {
    "status": validation["status"],
    "ignore_file": args.ignore_file,
    "ignore_mode": ignore_mode,
    "upload_file_count": validation["upload_file_count"],
    "forbidden_match_count": validation["forbidden_match_count"],
    "forbidden_matches": validation["forbidden_matches"],
    "missing_required_files": validation["missing_required_files"],
    "missing_required_prefixes": validation["missing_required_prefixes"],
    "too_few_files": validation["too_few_files"],
  }
  print(json.dumps(payload, ensure_ascii=False, indent=2))
  return 0 if validation["status"] == "ok" else 1


if __name__ == "__main__":
  raise SystemExit(main())
