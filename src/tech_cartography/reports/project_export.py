"""Project export helpers for retrieval outputs."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

CSV_COLUMNS = [
  "publication_number",
  "publication_date",
  "title",
  "abstract",
  "assignee",
  "country",
  "url",
  "cpc_codes",
  "ipc_codes",
  "search_intents",
  "query_plan_ids",
  "matched_terms",
  "source_type",
  "evidence_level",
  "claims_source",
  "description_source",
]


def _serialize_list_field(value: Any) -> str:
  if value is None:
    return ""
  if isinstance(value, list):
    return "; ".join(str(item) for item in value if str(item).strip())
  return str(value)


def _serialize_value(value: Any) -> str:
  if value is None:
    return ""
  if isinstance(value, (dict, list)):
    return json.dumps(value, ensure_ascii=False)
  return str(value)


def load_records_csv(path: str | Path) -> list[dict[str, Any]]:
  csv_path = Path(path)
  with csv_path.open(encoding="utf-8", newline="") as handle:
    return list(csv.DictReader(handle))


def _normalize_row_for_csv(record: dict[str, Any], fieldnames: list[str]) -> dict[str, str]:
  row = {column: "" for column in fieldnames}
  for key, value in record.items():
    if key not in row:
      continue
    if key in {
      "search_intents",
      "query_plan_ids",
      "matched_terms",
      "secondary_cluster_ids",
      "noise_signals",
      "independent_claims",
      "measured_properties",
      "warnings",
      "errors",
      "normalized_terms",
      "support_sections",
      "notes",
      "authors",
      "concepts",
      "keywords",
      "matched_terms",
      "reasons",
      "warnings",
      "evidence_basis",
      "strongest_supported_points",
      "weak_or_uncertain_points",
      "key_evidence_gaps",
    }:
      row[key] = _serialize_list_field(value)
    elif key in {"cluster_scores", "score_breakdown", "evidence_coverage"}:
      row[key] = _serialize_value(value)
    else:
      row[key] = "" if value is None else str(value)
  return row


def save_records_csv(records: list[dict[str, Any]], path: str | Path) -> str:
  output_path = Path(path)
  output_path.parent.mkdir(parents=True, exist_ok=True)
  fieldnames = list(CSV_COLUMNS)
  if records:
    for key in records[0].keys():
      if key not in fieldnames:
        fieldnames.append(key)
  with output_path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for record in records:
      writer.writerow(_normalize_row_for_csv(record, fieldnames))
  return str(output_path)


def save_retrieval_summary(summary: dict[str, Any], path: str | Path) -> str:
  output_path = Path(path)
  output_path.parent.mkdir(parents=True, exist_ok=True)
  with output_path.open("w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2, ensure_ascii=False)
  return str(output_path)


def build_output_directory(base_dir: str | Path) -> Path:
  timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
  output_dir = Path(base_dir) / timestamp
  output_dir.mkdir(parents=True, exist_ok=True)
  return output_dir
