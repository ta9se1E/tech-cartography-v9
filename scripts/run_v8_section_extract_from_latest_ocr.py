#!/usr/bin/env python3
"""Extract patent sections from latest Google Vision OCR output (Phase 27S.5.2)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
  sys.path.insert(0, str(SRC))

from tech_cartography.services.v8_patent_section_extract import (
  extract_sections_from_pdf_text_output,
  find_publication_fulltext_raw_pack,
  write_section_outputs,
)


def main() -> int:
  parser = argparse.ArgumentParser(
    description="Run section extraction from latest OCR publication_fulltext_raw.csv",
  )
  parser.add_argument("--case-id", required=True)
  parser.add_argument("--publication-number", default="")
  parser.add_argument("--output-root", default=str(PROJECT_ROOT / "outputs"))
  parser.add_argument("--dry-run", action="store_true")
  args = parser.parse_args()

  pub = args.publication_number.strip() or None
  pack = find_publication_fulltext_raw_pack(
    args.case_id,
    PROJECT_ROOT,
    publication_number=pub,
    prefer_ocr=True,
  )
  if not pack:
    print("ERROR: latest OCR publication_fulltext_raw.csv not found")
    return 1
  if pack.extraction_method != "google_vision_ocr":
    print(f"WARNING: selected pack method={pack.extraction_method} (expected google_vision_ocr)")

  print(f"case_id: {args.case_id}")
  print(f"publication_number: {pub or '(all in pack)'}")
  print(f"raw_csv_path: {pack.raw_csv_path}")
  print(f"extraction_method: {pack.extraction_method}")
  print(f"source_pages: {pack.total_rows}")
  print(f"source_chars: {pack.total_text_length}")

  if args.dry_run:
    print("dry-run: section extraction skipped")
    return 0

  output_root = Path(args.output_root)
  results = extract_sections_from_pdf_text_output(args.case_id, pack.raw_csv_path, output_root)
  out_dir = write_section_outputs(args.case_id, results, output_root)
  summary_csv = out_dir / "section_extraction_summary.csv"
  sections_csv = out_dir / "publication_fulltext_sections.csv"
  print(f"section_extraction_summary.csv: {summary_csv}")
  print(f"publication_fulltext_sections.csv: {sections_csv}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
