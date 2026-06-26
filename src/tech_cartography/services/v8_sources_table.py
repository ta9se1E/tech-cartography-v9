"""Sources table loader for v8 UI skeleton (Phase 27B)."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

SOURCE_CSV_COLUMNS: tuple[str, ...] = (
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


def project_root_from_here() -> Path:
  return Path(__file__).resolve().parents[3]


def list_case_ids(project_root: Path | str | None = None) -> list[str]:
  root = Path(project_root) if project_root else project_root_from_here()
  cases_dir = root / "cases"
  if not cases_dir.is_dir():
    return []
  return sorted(path.name for path in cases_dir.iterdir() if path.is_dir() and (path / "case_profile.yaml").exists())


def load_case_profile(case_id: str, project_root: Path | str | None = None) -> dict[str, Any] | None:
  root = Path(project_root) if project_root else project_root_from_here()
  path = root / "cases" / case_id / "case_profile.yaml"
  if not path.exists():
    return None
  try:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None
  except Exception:
    return None


def load_source_candidates(
  case_id: str | None = None,
  *,
  project_root: Path | str | None = None,
) -> list[dict[str, str]]:
  root = Path(project_root) if project_root else project_root_from_here()
  rows: list[dict[str, str]] = []
  case_ids = [case_id] if case_id else list_case_ids(root)
  for cid in case_ids:
    csv_path = root / "cases" / cid / "source_candidates.csv"
    if not csv_path.exists():
      continue
    with csv_path.open(encoding="utf-8", newline="") as handle:
      reader = csv.DictReader(handle)
      for row in reader:
        normalized = {col: str(row.get(col) or "").strip() for col in SOURCE_CSV_COLUMNS}
        if not normalized.get("case_id"):
          normalized["case_id"] = cid
        rows.append(normalized)
  return rows


def filter_patent_sources(rows: list[dict[str, str]]) -> list[dict[str, str]]:
  return [row for row in rows if str(row.get("type") or "").lower() == "patent"]


def sources_to_csv_text(rows: list[dict[str, str]]) -> str:
  buffer = io.StringIO()
  writer = csv.DictWriter(buffer, fieldnames=list(SOURCE_CSV_COLUMNS))
  writer.writeheader()
  for row in rows:
    writer.writerow({col: row.get(col, "") for col in SOURCE_CSV_COLUMNS})
  return buffer.getvalue()
