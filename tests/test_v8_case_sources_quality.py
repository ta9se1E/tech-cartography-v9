"""Quality checks for case source_candidates.csv (Phase 27C)."""

from __future__ import annotations

import csv
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_IDS = (
  "case_01_pan_graphitization",
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
)

REQUIRED_COLUMNS = (
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

FAKE_DOI_RE = re.compile(r"10\.(0000|1234)/|example\.com|fake|placeholder", re.IGNORECASE)


def _load_rows(case_id: str) -> list[dict[str, str]]:
  path = PROJECT_ROOT / "cases" / case_id / "source_candidates.csv"
  with path.open(encoding="utf-8", newline="") as handle:
    reader = csv.DictReader(handle)
    assert reader.fieldnames is not None
    for col in REQUIRED_COLUMNS:
      assert col in reader.fieldnames, f"{case_id} missing {col}"
    return list(reader)


def test_each_case_patent_paper_web_counts() -> None:
  for case_id in CASE_IDS:
    rows = _load_rows(case_id)
    types = [str(r.get("type") or "").lower() for r in rows]
    assert types.count("patent") >= 5, case_id
    assert types.count("paper") >= 2, case_id
    assert sum(1 for t in types if t in {"web", "web_signal", "company"}) >= 1, case_id


def test_no_obvious_fake_doi_in_csv() -> None:
  for case_id in CASE_IDS:
    for row in _load_rows(case_id):
      url = str(row.get("url") or "")
      notes = str(row.get("notes") or "")
      assert not FAKE_DOI_RE.search(url), f"fake-like url in {case_id}: {url}"
      assert not FAKE_DOI_RE.search(notes), f"fake-like notes in {case_id}"
