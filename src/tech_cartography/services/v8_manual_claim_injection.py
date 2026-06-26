"""v8 Manual Claim Injection service (Phase 27K)."""

from __future__ import annotations

import csv
import hashlib
import re
import shutil
from pathlib import Path
from typing import Any

from tech_cartography.runtime.v8_manual_claim_injection_schema import (
  MANUAL_CLAIM_SAFETY_NOTICES,
  VALID_CLAIM_SOURCE_TYPES,
  V8ManualClaimInjectionRequest,
  V8ManualClaimInjectionResult,
)
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_claim_input_loader import (
  CLAIMS_INPUT_COLUMNS,
  NOT_LOADED_MARKERS,
  claims_input_path,
  load_claims_input_csv,
)
from tech_cartography.services.v8_sources_table import load_case_profile, project_root_from_here

MIN_CLAIM_TEXT_LENGTH = 40

VALID_CASE_IDS: frozenset[str] = frozenset({
  "case_01_pan_graphitization",
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
})

PLACEHOLDER_PATTERNS: tuple[re.Pattern[str], ...] = (
  re.compile(r"claim\s*text\s*not\s*loaded", re.IGNORECASE),
  re.compile(r"claim\s*text\s*loading\s*required", re.IGNORECASE),
  re.compile(r"\bnot\s+loaded\b", re.IGNORECASE),
  re.compile(r"\bplaceholder\b", re.IGNORECASE),
  re.compile(r"\blorem\s+ipsum\b", re.IGNORECASE),
  re.compile(r"\btbd\b", re.IGNORECASE),
  re.compile(r"\btodo\b", re.IGNORECASE),
  re.compile(r"^test\s*fixture\s*only", re.IGNORECASE),
)


def _request_id(case_id: str, publication_number: str, claim_no: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{publication_number}|{claim_no}|inject".encode()).hexdigest()[:12]
  return f"{case_id}:inject:{digest}"


def _result_id(case_id: str, publication_number: str, claim_no: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{publication_number}|{claim_no}|result".encode()).hexdigest()[:12]
  return f"{case_id}:inject_result:{digest}"


def validate_claim_text(claim_text: str) -> tuple[str, str, list[str]]:
  """Return (status, normalized_text, warnings). Does not generate claim text."""
  warnings: list[str] = []
  normalized = " ".join(claim_text.split())
  stripped = normalized.strip()

  if not stripped:
    return "rejected_empty", "", warnings

  lowered = stripped.lower()
  if lowered in NOT_LOADED_MARKERS:
    return "rejected_placeholder", "", warnings + ["not_loaded marker rejected"]

  for pattern in PLACEHOLDER_PATTERNS:
    if pattern.search(stripped):
      return "rejected_placeholder", "", warnings + ["placeholder-like claim text rejected"]

  if len(stripped) < MIN_CLAIM_TEXT_LENGTH:
    return "rejected_too_short", "", warnings + [f"claim text too short (< {MIN_CLAIM_TEXT_LENGTH} chars)"]

  status = "manual_input"
  warnings.append("user provided claim text — not auto-generated")
  return status, stripped, warnings


def _normalize_source_type(claim_source_type: str) -> str:
  value = (claim_source_type or "manual").strip().lower()
  if value in VALID_CLAIM_SOURCE_TYPES:
    return value
  return "other_user_provided"


def _backup_claims_csv(csv_path: Path) -> str:
  if not csv_path.exists():
    return ""
  stamp = utc_now_iso().replace(":", "").replace("-", "").replace("+00:00", "Z")
  backup = csv_path.with_name(f"claims_input.csv.bak_{stamp}")
  shutil.copy2(csv_path, backup)
  return str(backup)


def _write_claims_csv(csv_path: Path, rows: list[dict[str, str]]) -> None:
  csv_path.parent.mkdir(parents=True, exist_ok=True)
  with csv_path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(CLAIMS_INPUT_COLUMNS))
    writer.writeheader()
    for row in rows:
      writer.writerow({col: row.get(col, "") for col in CLAIMS_INPUT_COLUMNS})


def list_claims_needing_text(
  case_id: str,
  *,
  project_root: Path | str | None = None,
) -> list[dict[str, Any]]:
  """Return publication numbers / claim rows that still need user-provided claim text."""
  rows, _ = load_claims_input_csv(case_id, project_root=project_root)
  needing: list[dict[str, Any]] = []
  for row in rows:
    if not row.has_loaded_text():
      needing.append({
        "case_id": row.case_id,
        "publication_number": row.publication_number,
        "patent_title": row.patent_title,
        "claim_no": row.claim_no,
        "claim_source_url": row.claim_source_url,
        "notes": row.notes,
      })
  return needing


def inject_manual_claim(
  *,
  case_id: str,
  publication_number: str,
  claim_no: str,
  claim_text: str,
  claim_source_type: str = "manual",
  claim_source_url: str = "",
  claim_source_path: str = "",
  user_note: str = "",
  patent_title: str = "",
  project_root: Path | str | None = None,
) -> V8ManualClaimInjectionResult:
  """Validate and save user-provided claim text to claims_input.csv. No external API calls."""
  root = Path(project_root or project_root_from_here())
  if case_id not in VALID_CASE_IDS:
    return V8ManualClaimInjectionResult(
      result_id=_result_id(case_id, publication_number, claim_no),
      case_id=case_id,
      publication_number=publication_number.strip(),
      claim_no=(claim_no or "1").strip(),
      claim_text_status="rejected_invalid_target",
      updated_claims_input_path=str(claims_input_path(case_id, root)),
      warnings=[f"invalid case_id: {case_id} — expected one of {sorted(VALID_CASE_IDS)}"],
      next_refresh_steps=["有効な case_id を指定してください"],
    )

  pub = publication_number.strip()
  cno = (claim_no or "1").strip()
  profile = load_case_profile(case_id, root) or {}
  title = patent_title.strip() or str(profile.get("case_name") or "")

  request = V8ManualClaimInjectionRequest(
    request_id=_request_id(case_id, pub, cno),
    case_id=case_id,
    publication_number=pub,
    patent_title=title,
    claim_no=cno,
    claim_text=claim_text,
    claim_source_type=_normalize_source_type(claim_source_type),
    claim_source_url=claim_source_url.strip(),
    claim_source_path=claim_source_path.strip(),
    user_note=user_note.strip(),
  )

  status, normalized, warnings = validate_claim_text(claim_text)
  if status.startswith("rejected"):
    return V8ManualClaimInjectionResult(
      result_id=_result_id(case_id, pub, cno),
      case_id=case_id,
      publication_number=pub,
      claim_no=cno,
      claim_text_status=status,
      normalized_claim_text="",
      claim_text_length=0,
      saved_to_claims_input_csv=False,
      updated_claims_input_path=str(claims_input_path(case_id, root)),
      warnings=warnings + list(MANUAL_CLAIM_SAFETY_NOTICES[:2]),
      next_refresh_steps=["有効な claim 本文を入力して再試行してください"],
    )

  csv_path = claims_input_path(case_id, root)
  backup_path = _backup_claims_csv(csv_path) if csv_path.exists() else ""

  existing_rows, _ = load_claims_input_csv(case_id, project_root=root)
  row_dicts: list[dict[str, str]] = []
  found = False
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
    if row.publication_number == pub and row.claim_no == cno:
      d["claim_text"] = normalized
      d["claim_source_type"] = request.claim_source_type
      if request.claim_source_url:
        d["claim_source_url"] = request.claim_source_url
      if request.claim_source_path:
        d["claim_source_path"] = request.claim_source_path
      note_parts = ["user provided claim text"]
      if user_note.strip():
        note_parts.append(user_note.strip())
      d["notes"] = "; ".join(note_parts)
      if title and not d["patent_title"]:
        d["patent_title"] = title
      found = True
    row_dicts.append(d)

  if not found:
    row_dicts.append({
      "case_id": case_id,
      "publication_number": pub,
      "patent_title": title,
      "claim_no": cno,
      "claim_text": normalized,
      "claim_source_type": request.claim_source_type,
      "claim_source_url": request.claim_source_url,
      "claim_source_path": request.claim_source_path,
      "notes": "; ".join(filter(None, ["user provided claim text", user_note.strip()])),
    })

  _write_claims_csv(csv_path, row_dicts)
  if backup_path:
    warnings.append(f"backup created: {backup_path}")

  return V8ManualClaimInjectionResult(
    result_id=_result_id(case_id, pub, cno),
    case_id=case_id,
    publication_number=pub,
    claim_no=cno,
    claim_text_status=status,
    normalized_claim_text=normalized,
    claim_text_length=len(normalized),
    saved_to_claims_input_csv=True,
    updated_claims_input_path=str(csv_path),
    backup_path=backup_path,
    warnings=warnings,
    next_refresh_steps=[
      "Claim Map を再生成",
      "Evidence Map を再生成",
      "Gap / Next Actions を再生成",
      "Fixed Point Observation を再生成",
      "Validation Pack を再評価",
    ],
  )


def claim_text_loaded_in_csv(
  case_id: str,
  publication_number: str,
  claim_no: str,
  *,
  project_root: Path | str | None = None,
) -> tuple[bool, str]:
  rows, _ = load_claims_input_csv(case_id, project_root=project_root)
  for row in rows:
    if row.publication_number == publication_number.strip() and row.claim_no == (claim_no or "1").strip():
      if row.has_loaded_text():
        return True, row.claim_text
      return False, ""
  return False, ""
