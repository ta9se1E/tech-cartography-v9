"""Load and normalize v8 source_candidates.csv rows (Phase 27C)."""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from tech_cartography.runtime.v8_sources_schema import V8SourceRecord, utc_now_iso
from tech_cartography.services.v8_sources_table import (
  SOURCE_CSV_COLUMNS,
  list_case_ids,
  load_case_profile,
  project_root_from_here,
)

_TYPE_MAP: dict[str, str] = {
  "patent": "patent",
  "paper": "paper",
  "web": "web",
  "web_signal": "web",
  "company": "company",
  "pdf": "pdf",
  "csv": "csv",
  "manual": "manual",
}

_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s]+", re.IGNORECASE)


def normalize_source_type(raw: str) -> str:
  key = str(raw or "").strip().lower()
  return _TYPE_MAP.get(key, "unknown")


def extract_doi(url: str, explicit: str = "") -> str:
  if explicit.strip():
    return explicit.strip()
  match = _DOI_RE.search(url or "")
  return match.group(0) if match else ""


def normalize_source_status(raw: str, source_type: str) -> str:
  value = str(raw or "").strip().lower()
  if value in {"verified_primary", "primary_candidate"}:
    return "primary_candidate"
  if value in {"candidate", "supporting_candidate"}:
    return "supporting_candidate"
  if value in {"candidate_information_only", "weak_signal"}:
    return "weak_signal"
  if value in {"manual_review_required", "uploaded", "excluded"}:
    return value
  if source_type in {"web", "company"}:
    return "weak_signal"
  return value or "supporting_candidate"


def normalize_evidence_role(raw: str, source_type: str) -> str:
  value = str(raw or "").strip()
  if value:
    return value
  if source_type == "web":
    return "web_signal"
  if source_type == "company":
    return "company_signal"
  if source_type == "paper":
    return "paper_evidence"
  if source_type == "patent":
    return "claim_source"
  return "unknown"


def _stable_hash(text: str) -> str:
  return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def build_source_id(
  *,
  case_id: str,
  source_type: str,
  publication_number: str,
  doi: str,
  url: str,
  title: str,
) -> str:
  pub = publication_number.strip().upper()
  if pub:
    key = f"{case_id}|{source_type}|pub|{pub}"
  elif doi:
    key = f"{case_id}|{source_type}|doi|{doi.lower()}"
  elif url.strip():
    key = f"{case_id}|{source_type}|url|{url.strip().lower()}"
  else:
    key = f"{case_id}|{source_type}|title|{title.strip().lower()}"
  return f"{case_id}:{source_type}:{_stable_hash(key)}"


def _reliability_label(
  *,
  source_type: str,
  publication_number: str,
  doi: str,
  url: str,
  source_status: str,
) -> str:
  if source_status in {"weak_signal", "manual_review_required", "excluded"}:
    return "weak"
  if source_type == "patent" and publication_number.strip():
    return "primary"
  if source_type == "paper" and (doi or url.strip()):
    return "secondary"
  if source_type in {"web", "company"}:
    return "candidate"
  if url.strip():
    return "candidate"
  return "unknown"


def _verification_status(*, url: str, human_review_required: bool) -> str:
  if human_review_required:
    return "needs_human_review"
  if url.strip():
    return "source_url_available"
  return "unverified"


def _candidate_information_only(source_type: str, source_status: str, evidence_role: str) -> bool:
  if source_type in {"web", "company"}:
    return True
  if source_status == "weak_signal":
    return True
  if "candidate" in evidence_role.lower() or evidence_role in {"web_signal", "company_signal", "background_context"}:
    return True
  return False


def load_csv_rows(
  case_id: str,
  *,
  project_root: Path | str | None = None,
) -> tuple[list[dict[str, str]], list[str]]:
  root = Path(project_root) if project_root else project_root_from_here()
  csv_path = root / "cases" / case_id / "source_candidates.csv"
  warnings: list[str] = []
  if not csv_path.exists():
    return [], [f"missing source_candidates.csv for {case_id}"]

  rows: list[dict[str, str]] = []
  with csv_path.open(encoding="utf-8", newline="") as handle:
    reader = csv.DictReader(handle)
    fieldnames = reader.fieldnames or []
    missing = [col for col in SOURCE_CSV_COLUMNS if col not in fieldnames]
    if missing:
      warnings.append(f"{case_id}: missing columns {', '.join(missing)} — filled with empty values")
    for row in reader:
      normalized = {col: str(row.get(col) or "").strip() for col in SOURCE_CSV_COLUMNS}
      if not normalized.get("case_id"):
        normalized["case_id"] = case_id
      rows.append(normalized)
  return rows, warnings


def csv_row_to_source_record(row: dict[str, str], *, project_root: Path) -> V8SourceRecord:
  case_id = row.get("case_id", "")
  source_type = normalize_source_type(row.get("type", ""))
  url = row.get("url", "").strip()
  doi = extract_doi(url)
  publication_number = row.get("publication_number", "").strip()
  source_status = normalize_source_status(row.get("source_status", ""), source_type)
  evidence_role = normalize_evidence_role(row.get("evidence_role", ""), source_type)
  human_review_required = not url and source_type in {"patent", "paper", "manual", "unknown"}
  if "manual review" in row.get("notes", "").lower():
    human_review_required = True
    source_status = "manual_review_required"

  profile = load_case_profile(case_id, project_root) or {}
  theme = str(profile.get("theme") or "")
  claim_axes = list(profile.get("expected_claim_axes") or [])

  csv_path = project_root / "cases" / case_id / "source_candidates.csv"
  return V8SourceRecord(
    source_id=build_source_id(
      case_id=case_id,
      source_type=source_type,
      publication_number=publication_number,
      doi=doi,
      url=url,
      title=row.get("title", ""),
    ),
    case_id=case_id,
    source_type=source_type,
    title=row.get("title", ""),
    organization=row.get("organization", ""),
    year=row.get("year", ""),
    url=url,
    publication_number=publication_number,
    doi=doi,
    source_status=source_status,
    evidence_role=evidence_role,
    reliability_label=_reliability_label(
      source_type=source_type,
      publication_number=publication_number,
      doi=doi,
      url=url,
      source_status=source_status,
    ),
    verification_status=_verification_status(url=url, human_review_required=human_review_required),
    candidate_information_only=_candidate_information_only(source_type, source_status, evidence_role),
    human_review_required=human_review_required,
    related_claim_axes=claim_axes,
    related_case_theme=theme,
    source_file_path=str(csv_path) if csv_path.exists() else "",
    artifact_path="",
    notes=row.get("notes", ""),
    created_at=utc_now_iso(),
  )


def dedupe_key(record: V8SourceRecord) -> str:
  pub = record.publication_number.strip().upper()
  if pub:
    return f"pub:{pub}"
  if record.doi:
    return f"doi:{record.doi.lower()}"
  if record.url.strip():
    parsed = urlparse(record.url.strip().lower())
    return f"url:{parsed.netloc}{parsed.path}"
  return f"title:{record.title.strip().lower()}|{record.organization.strip().lower()}|{record.year}"


def load_source_records(
  case_id: str | None = None,
  *,
  project_root: Path | str | None = None,
) -> tuple[list[V8SourceRecord], list[str]]:
  root = Path(project_root) if project_root else project_root_from_here()
  case_ids = [case_id] if case_id else list_case_ids(root)
  records: list[V8SourceRecord] = []
  warnings: list[str] = []
  for cid in case_ids:
    rows, row_warnings = load_csv_rows(cid, project_root=root)
    warnings.extend(row_warnings)
    for row in rows:
      records.append(csv_row_to_source_record(row, project_root=root))
  return records, warnings
