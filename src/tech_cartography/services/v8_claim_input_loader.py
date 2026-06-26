"""v8 Claim input loader (Phase 27E)."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tech_cartography.services.v8_patent_shortlist_export import find_latest_patent_shortlist_dir
from tech_cartography.services.v8_sources_table import project_root_from_here

CLAIMS_INPUT_COLUMNS: tuple[str, ...] = (
  "case_id",
  "publication_number",
  "patent_title",
  "claim_no",
  "claim_text",
  "claim_source_type",
  "claim_source_url",
  "claim_source_path",
  "notes",
)

NOT_LOADED_MARKERS: frozenset[str] = frozenset({
  "",
  "claim text not loaded",
  "claim text loading required",
})


@dataclass
class V8ClaimInputRow:
  case_id: str
  publication_number: str
  patent_title: str = ""
  claim_no: str = ""
  claim_text: str = ""
  claim_source_type: str = "unavailable"
  claim_source_url: str = ""
  claim_source_path: str = ""
  notes: str = ""
  warnings: list[str] = field(default_factory=list)

  def has_loaded_text(self) -> bool:
    return self.claim_text.strip().lower() not in NOT_LOADED_MARKERS

  def to_dict(self) -> dict[str, Any]:
    return {
      "case_id": self.case_id,
      "publication_number": self.publication_number,
      "patent_title": self.patent_title,
      "claim_no": self.claim_no,
      "claim_text": self.claim_text,
      "claim_source_type": self.claim_source_type,
      "claim_source_url": self.claim_source_url,
      "claim_source_path": self.claim_source_path,
      "notes": self.notes,
      "warnings": self.warnings,
    }


def claims_input_path(case_id: str, project_root: Path | str | None = None) -> Path:
  root = Path(project_root) if project_root else project_root_from_here()
  return root / "cases" / case_id / "claims_input.csv"


def load_claims_input_csv(
  case_id: str,
  *,
  project_root: Path | str | None = None,
) -> tuple[list[V8ClaimInputRow], list[str]]:
  path = claims_input_path(case_id, project_root)
  warnings: list[str] = []
  if not path.exists():
    return [], [f"claims_input.csv not found: {path.relative_to(Path(project_root or project_root_from_here()))}"]

  rows: list[V8ClaimInputRow] = []
  with path.open(encoding="utf-8", newline="") as handle:
    reader = csv.DictReader(handle)
    fieldnames = reader.fieldnames or []
    missing = [col for col in CLAIMS_INPUT_COLUMNS if col not in fieldnames]
    if missing:
      warnings.append(f"claims_input.csv missing columns: {', '.join(missing)}")

    for line_no, raw in enumerate(reader, start=2):
      pub = str(raw.get("publication_number") or "").strip()
      if not pub:
        warnings.append(f"claims_input.csv line {line_no}: empty publication_number")
      claim_no = str(raw.get("claim_no") or "").strip()
      if not claim_no:
        warnings.append(f"claims_input.csv line {line_no}: empty claim_no for {pub or '(no pub)'}")

      claim_text = str(raw.get("claim_text") or "").strip()
      source_type = str(raw.get("claim_source_type") or "unavailable").strip()
      row_warnings: list[str] = []
      if not claim_text or claim_text.lower() in NOT_LOADED_MARKERS:
        row_warnings.append("claim text not loaded")

      rows.append(
        V8ClaimInputRow(
          case_id=str(raw.get("case_id") or case_id).strip(),
          publication_number=pub,
          patent_title=str(raw.get("patent_title") or "").strip(),
          claim_no=claim_no or "1",
          claim_text=claim_text,
          claim_source_type=source_type,
          claim_source_url=str(raw.get("claim_source_url") or "").strip(),
          claim_source_path=str(raw.get("claim_source_path") or "").strip(),
          notes=str(raw.get("notes") or "").strip(),
          warnings=row_warnings,
        ),
      )

  return rows, warnings


def merge_manual_claim_inputs(
  manual_rows: list[dict[str, Any]],
  *,
  case_id: str,
) -> list[V8ClaimInputRow]:
  merged: list[V8ClaimInputRow] = []
  for raw in manual_rows:
    claim_text = str(raw.get("claim_text") or "").strip()
    merged.append(
      V8ClaimInputRow(
        case_id=case_id,
        publication_number=str(raw.get("publication_number") or "").strip(),
        patent_title=str(raw.get("patent_title") or "").strip(),
        claim_no=str(raw.get("claim_no") or "1").strip(),
        claim_text=claim_text,
        claim_source_type="manual",
        claim_source_url=str(raw.get("claim_source_url") or "").strip(),
        claim_source_path="",
        notes=str(raw.get("notes") or "manual UI input").strip(),
        warnings=[] if claim_text else ["claim text not loaded"],
      ),
    )
  return merged


def reference_patent_shortlist_artifact(
  case_id: str,
  *,
  project_root: Path | str | None = None,
) -> str:
  shortlist_dir = find_latest_patent_shortlist_dir(case_id, project_root)
  if shortlist_dir and shortlist_dir.exists():
    manifest = shortlist_dir / "patent_shortlist_manifest.json"
    if manifest.exists():
      return str(manifest)
    return str(shortlist_dir)
  return ""


def load_claim_inputs(
  case_id: str,
  *,
  project_root: Path | str | None = None,
  manual_rows: list[dict[str, Any]] | None = None,
) -> tuple[list[V8ClaimInputRow], list[str], list[str]]:
  """Return rows, warnings, artifact_paths."""
  csv_rows, csv_warnings = load_claims_input_csv(case_id, project_root=project_root)
  artifact_paths: list[str] = []
  shortlist_ref = reference_patent_shortlist_artifact(case_id, project_root=project_root)
  if shortlist_ref:
    artifact_paths.append(shortlist_ref)

  manual = merge_manual_claim_inputs(manual_rows or [], case_id=case_id)
  by_key: dict[tuple[str, str], V8ClaimInputRow] = {}
  for row in csv_rows:
    by_key[(row.publication_number, row.claim_no)] = row
  for row in manual:
    key = (row.publication_number, row.claim_no)
    if row.has_loaded_text() or key not in by_key:
      by_key[key] = row

  return list(by_key.values()), csv_warnings, artifact_paths
