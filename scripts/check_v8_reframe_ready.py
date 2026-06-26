#!/usr/bin/env python3
"""Phase27A readiness check for v8 reframe and three-case validation plan."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DOCS = (
  "docs/v8_product_reframe.md",
  "docs/v8_three_case_validation_plan.md",
  "docs/v8_user_flow_and_tabs.md",
  "docs/v8_cursor_roadmap.md",
  "README_v8_LOCAL_FIRST.md",
)

CASE_IDS = (
  "case_01_pan_graphitization",
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
)

CASE_FILES = (
  "case_profile.yaml",
  "source_candidates.csv",
  "expected_outputs.md",
  "validation_checklist.md",
)

CSV_COLUMNS = (
  "type",
  "title",
  "organization",
  "year",
  "url",
  "publication_number",
  "source_status",
  "evidence_role",
  "case_id",
  "notes",
)

DOC_KEYWORD_CHECKS: tuple[tuple[str, tuple[str, ...]], ...] = (
  (
    "email send required for fixed point observation",
    ("メール送信", "定点観測"),
  ),
  (
    "scheduler required for fixed point observation",
    ("Scheduler", "定点観測"),
  ),
  (
    "watch profile / scope feedback / run history",
    ("Watch Profile", "Scope Feedback", "Run History"),
  ),
  (
    "local-first development",
    ("ローカル", "local-first"),
  ),
  (
    "no FTO/infringement/validity/legal judgement",
    ("FTO", "侵害", "有効性"),
  ),
  (
    "no fake evidence",
    ("架空", "fake"),
  ),
  (
    "cloud build only at milestones",
    ("Cloud Build", "節目"),
  ),
)


def _read(path: Path) -> str:
  if not path.exists():
    return ""
  return path.read_text(encoding="utf-8")


def _check_file_exists(path: Path, failures: list[str]) -> bool:
  if path.exists():
    print(f"PASS: artifact exists: {path.relative_to(PROJECT_ROOT)}")
    return True
  failures.append(f"missing file: {path.relative_to(PROJECT_ROOT)}")
  return False


def _docs_blob() -> str:
  parts: list[str] = []
  for rel in REQUIRED_DOCS:
    parts.append(_read(PROJECT_ROOT / rel))
  return "\n".join(parts)


def _keyword_present(blob: str, keywords: tuple[str, ...]) -> bool:
  lowered = blob.lower()
  return any(kw.lower() in lowered for kw in keywords)


def main(argv: list[str] | None = None) -> int:
  del argv
  failures: list[str] = []

  print("v8 reframe readiness:")

  for rel in REQUIRED_DOCS:
    _check_file_exists(PROJECT_ROOT / rel, failures)

  for case_id in CASE_IDS:
    case_dir = PROJECT_ROOT / "cases" / case_id
    for name in CASE_FILES:
      _check_file_exists(case_dir / name, failures)

    csv_path = case_dir / "source_candidates.csv"
    if csv_path.exists():
      with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing_cols = [col for col in CSV_COLUMNS if col not in fieldnames]
        if missing_cols:
          failures.append(
            f"{case_id}/source_candidates.csv missing columns: {', '.join(missing_cols)}"
          )
        else:
          print(f"PASS: {case_id}/source_candidates.csv has required columns")

  blob = _docs_blob()
  for label, keywords in DOC_KEYWORD_CHECKS:
    if _keyword_present(blob, keywords):
      print(f"PASS: docs mention {label}")
    else:
      failures.append(f"docs missing keyword group for: {label} ({keywords})")

  if failures:
    print("\nFAILURES:")
    for item in failures:
      print(f"  - {item}")
    print(f"\nv8 reframe readiness: FAIL ({len(failures)} issue(s))")
    return 1

  print("\nv8 reframe readiness: PASS")
  return 0


if __name__ == "__main__":
  sys.exit(main())
