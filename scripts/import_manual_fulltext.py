#!/usr/bin/env python3
"""Import manual claims/description from local text files (Phase 18B)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.manual.manual_fulltext_input_schema import (
  ManualFulltextInput,
  save_manual_fulltext_input,
  validate_manual_fulltext_input,
)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Import manual fulltext from files or inline text")
  parser.add_argument("--publication-number", required=True)
  parser.add_argument("--source-url", default="")
  parser.add_argument("--claims-file", default="")
  parser.add_argument("--description-file", default="")
  parser.add_argument("--claims-text", default="")
  parser.add_argument("--description-text", default="")
  parser.add_argument("--input-route", default="manual_google_patents", choices=[
    "manual_google_patents",
    "manual_pdf",
    "manual_user_paste",
  ])
  parser.add_argument("--entered-by", default="local_user")
  parser.add_argument("--source-note", default="")
  parser.add_argument("--output-dir", default="outputs/manual_fulltext_inputs")
  parser.add_argument("--validate-only", action="store_true", default=False)
  return parser.parse_args()


def _read_optional_file(path: str) -> str:
  if not path:
    return ""
  file_path = Path(path)
  if not file_path.exists():
    raise FileNotFoundError(f"File not found: {path}")
  return file_path.read_text(encoding="utf-8")


def main() -> int:
  args = parse_args()
  claims_text = args.claims_text or _read_optional_file(args.claims_file)
  description_text = args.description_text or _read_optional_file(args.description_file)

  entry = ManualFulltextInput(
    publication_number=args.publication_number,
    source_url=args.source_url or None,
    claims_text=claims_text or None,
    description_text=description_text or None,
    source_note=args.source_note or None,
    entered_by=args.entered_by,
    input_route=args.input_route,
  )
  validation = validate_manual_fulltext_input(entry)
  entry.validation_status = validation["validation_status"]
  entry.input_scope = str(validation.get("input_scope") or "claims_only")

  payload = {
    "publication_number": entry.publication_number,
    "validation_status": validation["validation_status"],
    "claims_present": validation.get("claims_present"),
    "description_present": validation.get("description_present"),
    "warnings": validation.get("warnings", []),
  }

  if args.validate_only:
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0

  path = save_manual_fulltext_input(entry, args.output_dir)
  payload["saved_path"] = path
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
