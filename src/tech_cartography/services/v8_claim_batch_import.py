"""Claim CSV/Excel batch import service (Phase 27Q.1)."""

from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path
from typing import Any

from tech_cartography.runtime.v8_claim_batch_import_schema import (
  CLAIM_BATCH_SAFETY_NOTICES,
  ClaimBatchImportReport,
  ClaimBatchRow,
  TEMPLATE_COLUMNS,
  VALID_DUPLICATE_MODES,
)
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_claim_input_loader import (
  CLAIMS_INPUT_COLUMNS,
  load_claims_input_csv,
)
from tech_cartography.services.v8_manual_claim_injection import (
  _backup_claims_csv,
  _normalize_source_type,
  _write_claims_csv,
  validate_claim_text,
)
from tech_cartography.services.v8_sources_table import project_root_from_here

TOP5_CLAIM_TEMPLATE_ROWS: tuple[dict[str, str], ...] = (
  {
    "publication_number": "CN117987966A",
    "claim_no": "1",
    "claim_text": "",
    "claim_source_url": "https://patents.google.com/patent/CN117987966A/en",
    "claim_source_type": "manual",
    "user_note": "user copied from Google Patents",
  },
  {
    "publication_number": "CN105401262A",
    "claim_no": "1",
    "claim_text": "",
    "claim_source_url": "https://patents.google.com/patent/CN105401262A/en",
    "claim_source_type": "manual",
    "user_note": "user copied from Google Patents",
  },
  {
    "publication_number": "CN105506785B",
    "claim_no": "1",
    "claim_text": "",
    "claim_source_url": "https://patents.google.com/patent/CN105506785B/en",
    "claim_source_type": "manual",
    "user_note": "user copied from Google Patents",
  },
  {
    "publication_number": "CN109402791B",
    "claim_no": "1",
    "claim_text": "",
    "claim_source_url": "https://patents.google.com/patent/CN109402791B/en",
    "claim_source_type": "manual",
    "user_note": "user copied from Google Patents",
  },
)


def _report_id(case_id: str, input_file: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{input_file}|batch".encode()).hexdigest()[:12]
  return f"{case_id}:claim_batch:{digest}"


def claim_batch_template_csv_text() -> str:
  buffer = io.StringIO()
  writer = csv.DictWriter(buffer, fieldnames=list(TEMPLATE_COLUMNS))
  writer.writeheader()
  for row in TOP5_CLAIM_TEMPLATE_ROWS:
    writer.writerow({col: row.get(col, "") for col in TEMPLATE_COLUMNS})
  return buffer.getvalue()


def _read_rows_from_path(path: Path) -> list[dict[str, str]]:
  suffix = path.suffix.lower()
  if suffix == ".csv":
    with path.open(encoding="utf-8-sig", newline="") as handle:
      return list(csv.DictReader(handle))
  if suffix in {".xlsx", ".xlsm"}:
    try:
      import openpyxl
    except ImportError as exc:
      raise ImportError("openpyxl required for Excel import") from exc
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    headers = [str(h or "").strip() for h in next(rows_iter, [])]
    out: list[dict[str, str]] = []
    for values in rows_iter:
      out.append({headers[i]: str(values[i] or "").strip() for i in range(len(headers))})
    return out
  raise ValueError(f"unsupported file type: {suffix}")


def _parse_upload_rows(raw_rows: list[dict[str, str]], *, source_file: str) -> list[ClaimBatchRow]:
  parsed: list[ClaimBatchRow] = []
  for idx, raw in enumerate(raw_rows, start=2):
    pub = str(raw.get("publication_number") or "").strip()
    claim_no = str(raw.get("claim_no") or "1").strip() or "1"
    claim_text = str(raw.get("claim_text") or "").strip()
    row = ClaimBatchRow(
      row_number=idx,
      publication_number=pub,
      claim_no=claim_no,
      claim_text=claim_text,
      claim_source_url=str(raw.get("claim_source_url") or "").strip(),
      claim_source_type=str(raw.get("claim_source_type") or "manual").strip() or "manual",
      user_note=str(raw.get("user_note") or "").strip(),
      patent_title=str(raw.get("patent_title") or "").strip(),
      language=str(raw.get("language") or "").strip(),
      source_file_name=str(raw.get("source_file_name") or source_file).strip(),
    )
    if not pub:
      row.status = "rejected"
      row.reject_reason = "empty publication_number"
    else:
      status, normalized, warnings = validate_claim_text(claim_text)
      if status.startswith("rejected"):
        row.status = "rejected"
        row.reject_reason = "; ".join(warnings) or status
      else:
        row.claim_text = normalized
        row.status = "valid"
    parsed.append(row)
  return parsed


def validate_claim_batch_import(
  *,
  case_id: str,
  input_path: Path | str,
  duplicate_mode: str = "update",
  project_root: Path | str | None = None,
) -> ClaimBatchImportReport:
  root = Path(project_root or project_root_from_here())
  path = Path(input_path)
  if duplicate_mode not in VALID_DUPLICATE_MODES:
    duplicate_mode = "update"

  raw = _read_rows_from_path(path)
  rows = _parse_upload_rows(raw, source_file=path.name)
  valid = [r for r in rows if r.status == "valid"]
  rejected = [r for r in rows if r.status == "rejected"]

  existing, _ = load_claims_input_csv(case_id, project_root=root)
  existing_keys = {(r.publication_number, r.claim_no): r for r in existing}

  skipped = 0
  would_update = 0
  for row in valid:
    key = (row.publication_number, row.claim_no)
    if key in existing_keys and existing_keys[key].has_loaded_text():
      if duplicate_mode == "skip":
        skipped += 1
      elif duplicate_mode == "update":
        would_update += 1

  return ClaimBatchImportReport(
    report_id=_report_id(case_id, str(path)),
    case_id=case_id,
    input_file=str(path),
    mode="validate",
    duplicate_mode=duplicate_mode,
    total_rows=len(rows),
    valid_rows=len(valid),
    rejected_rows=len(rejected),
    applied_rows=0,
    skipped_rows=skipped,
    updated_rows=would_update,
    warnings=list(CLAIM_BATCH_SAFETY_NOTICES[:2]),
    rows=valid,
    rejected=rejected,
  )


def apply_claim_batch_import(
  *,
  case_id: str,
  input_path: Path | str,
  duplicate_mode: str = "update",
  project_root: Path | str | None = None,
) -> ClaimBatchImportReport:
  report = validate_claim_batch_import(
    case_id=case_id,
    input_path=input_path,
    duplicate_mode=duplicate_mode,
    project_root=project_root,
  )
  if report.valid_rows == 0:
    report.warnings.append("valid rows 0 — claims_input.csv は更新しません")
    return report

  root = Path(project_root or project_root_from_here())
  from tech_cartography.services.v8_claim_input_loader import claims_input_path

  csv_path = claims_input_path(case_id, root)
  backup = _backup_claims_csv(csv_path) if csv_path.exists() else ""
  existing_rows, _ = load_claims_input_csv(case_id, project_root=root)
  row_dicts: list[dict[str, str]] = []
  by_key: dict[tuple[str, str], dict[str, str]] = {}

  for row in existing_rows:
    d = {col: "" for col in CLAIMS_INPUT_COLUMNS}
    d.update({
      "case_id": row.case_id or case_id,
      "publication_number": row.publication_number,
      "patent_title": row.patent_title,
      "claim_no": row.claim_no,
      "claim_text": row.claim_text,
      "claim_source_type": row.claim_source_type,
      "claim_source_url": row.claim_source_url,
      "claim_source_path": row.claim_source_path,
      "notes": row.notes,
    })
    by_key[(row.publication_number, row.claim_no)] = d

  applied = 0
  skipped = 0
  updated = 0
  for batch_row in report.rows:
    key = (batch_row.publication_number, batch_row.claim_no)
    if key in by_key and by_key[key].get("claim_text", "").strip() and duplicate_mode == "skip":
      skipped += 1
      continue
    if key in by_key and duplicate_mode == "append":
      skipped += 1
      continue
    note_parts = ["user provided claim text — batch import"]
    if batch_row.user_note:
      note_parts.append(batch_row.user_note)
    new_d = {
      "case_id": case_id,
      "publication_number": batch_row.publication_number,
      "patent_title": batch_row.patent_title or by_key.get(key, {}).get("patent_title", ""),
      "claim_no": batch_row.claim_no,
      "claim_text": batch_row.claim_text,
      "claim_source_type": _normalize_source_type(batch_row.claim_source_type),
      "claim_source_url": batch_row.claim_source_url,
      "claim_source_path": "",
      "notes": "; ".join(note_parts),
    }
    if key in by_key:
      updated += 1
    else:
      applied += 1
    by_key[key] = new_d

  row_dicts = list(by_key.values())
  _write_claims_csv(csv_path, row_dicts)

  report.mode = "apply"
  report.applied_rows = applied
  report.updated_rows = updated
  report.skipped_rows = skipped
  report.backup_path = backup
  report.updated_claims_input_path = str(csv_path)
  if backup:
    report.warnings.append(f"backup created: {backup}")
  return report
