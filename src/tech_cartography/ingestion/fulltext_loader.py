"""Manual full text file ingestion."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

SECTION_PATTERNS: dict[str, re.Pattern[str]] = {
  "claims": re.compile(r"(?im)^(?:#+\s*)?(?:claims?|請求項)\s*:?\s*$"),
  "description": re.compile(r"(?im)^(?:#+\s*)?(?:description|detailed description|明細書)\s*:?\s*$"),
  "examples": re.compile(r"(?im)^(?:#+\s*)?(?:examples?|embodiment|実施例|比較例)\s*:?\s*$"),
  "measured_properties": re.compile(
    r"(?im)^(?:#+\s*)?(?:measured properties|properties|物性)\s*:?\s*$",
  ),
}


def infer_sections_from_text(text: str) -> dict[str, str]:
  lines = text.splitlines()
  sections: dict[str, list[str]] = {
    "claims": [],
    "description": [],
    "examples": [],
    "measured_properties": [],
  }
  current = "description"
  for line in lines:
    stripped = line.strip()
    if not stripped:
      continue
    switched = False
    for key, pattern in SECTION_PATTERNS.items():
      if pattern.match(stripped):
        current = key
        switched = True
        break
    if not switched:
      sections[current].append(line)
  return {key: "\n".join(value).strip() for key, value in sections.items()}


def parse_fulltext_text(publication_number: str, text: str) -> dict[str, Any]:
  sections = infer_sections_from_text(text)
  measured = [
    item.strip()
    for item in re.findall(
      r"\b\d+(?:\.\d+)?\s*(?:MPa|GPa|cN/dtex|Pa|%)\b",
      text,
      flags=re.IGNORECASE,
    )
  ]
  return {
    "publication_number": publication_number,
    "claims": sections.get("claims") or None,
    "description": sections.get("description") or text,
    "examples": sections.get("examples") or None,
    "measured_properties": measured,
    "source_note": "manual_text_upload",
  }


def normalize_manual_fulltext_record(record: dict[str, Any]) -> dict[str, Any]:
  independent_claims = record.get("independent_claims")
  if isinstance(independent_claims, str):
    independent_claims = [part.strip() for part in independent_claims.split(";") if part.strip()]
  measured = record.get("measured_properties")
  if isinstance(measured, str):
    measured = [part.strip() for part in re.split(r"[;,\n]", measured) if part.strip()]
  return {
    "publication_number": str(record.get("publication_number", "")).strip(),
    "title": record.get("title"),
    "claims": record.get("claims"),
    "independent_claims": list(independent_claims or []),
    "description": record.get("description"),
    "examples": record.get("examples"),
    "measured_properties": list(measured or []),
    "source_url": record.get("source_url"),
    "source_note": record.get("source_note"),
  }


def load_fulltext_file(path: str) -> list[dict[str, Any]]:
  file_path = Path(path)
  suffix = file_path.suffix.lower()
  if suffix in {".txt", ".md"}:
    text = file_path.read_text(encoding="utf-8")
    pub_match = re.search(r"(US[\w\-]+|JP[\w\-]+|EP[\w\-]+|WO[\w\-]+)", text, re.IGNORECASE)
    publication_number = pub_match.group(1) if pub_match else file_path.stem
    return [normalize_manual_fulltext_record(parse_fulltext_text(publication_number, text))]
  if suffix == ".csv":
    with file_path.open(encoding="utf-8", newline="") as handle:
      return [normalize_manual_fulltext_record(row) for row in csv.DictReader(handle)]
  if suffix == ".xlsx":
    try:
      import openpyxl
    except ImportError as exc:
      raise RuntimeError("openpyxl is required for XLSX ingestion") from exc
    workbook = openpyxl.load_workbook(file_path, read_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
      return []
    headers = [str(item or "").strip() for item in rows[0]]
    records: list[dict[str, Any]] = []
    for row in rows[1:]:
      record = {
        headers[index]: ("" if value is None else str(value))
        for index, value in enumerate(row)
        if index < len(headers) and headers[index]
      }
      if record.get("publication_number"):
        records.append(normalize_manual_fulltext_record(record))
    return records
  raise ValueError(f"Unsupported full text file type: {suffix}")
