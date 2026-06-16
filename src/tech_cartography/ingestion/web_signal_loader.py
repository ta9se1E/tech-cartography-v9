"""Load and normalize web / company signal input files."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

import yaml

from tech_cartography.domain.web_signal import WebSignal, new_signal_id
from tech_cartography.evidence.company_name_normalizer import normalize_company_name


def _parse_terms(value: Any) -> list[str]:
  if isinstance(value, list):
    return [str(item).strip() for item in value if str(item).strip()]
  if isinstance(value, str):
    return [part.strip() for part in re.split(r"[;,]", value) if part.strip()]
  return []


def normalize_web_signal_record(record: dict[str, Any]) -> dict[str, Any]:
  warnings: list[str] = []
  company = str(record.get("company") or "").strip()
  source_url = str(record.get("source_url") or "").strip() or None
  signal_type = str(record.get("signal_type") or "").strip() or "unknown"
  confidence_raw = record.get("confidence")
  try:
    confidence = float(confidence_raw) if confidence_raw not in (None, "") else 0.5
  except (TypeError, ValueError):
    confidence = 0.5
    warnings.append("Invalid confidence value; defaulted to 0.5")

  if not source_url:
    warnings.append("Missing source_url")

  display_url = source_url
  signal = WebSignal(
    signal_id=str(record.get("signal_id") or new_signal_id()),
    company=company,
    normalized_company=normalize_company_name(company),
    source_title=str(record.get("source_title") or record.get("title") or "").strip(),
    signal_type=signal_type,
    signal_date=str(record.get("signal_date") or "").strip() or None,
    source_url=source_url,
    source_name=str(record.get("source_name") or "").strip() or None,
    display_url=display_url,
    technology_terms=_parse_terms(record.get("technology_terms")),
    summary=str(record.get("summary") or "").strip() or None,
    business_signal=str(record.get("business_signal") or "").strip() or None,
    confidence=confidence,
    source_note=str(record.get("source_note") or "").strip() or None,
    warnings=warnings,
  )
  return signal.to_dict()


def load_web_signals_from_csv(path: str) -> list[dict[str, Any]]:
  with Path(path).open(encoding="utf-8", newline="") as handle:
    return [normalize_web_signal_record(row) for row in csv.DictReader(handle)]


def load_web_signals_from_json(path: str) -> list[dict[str, Any]]:
  with Path(path).open(encoding="utf-8") as handle:
    data = json.load(handle)
  if isinstance(data, list):
    records = data
  elif isinstance(data, dict) and isinstance(data.get("signals"), list):
    records = data["signals"]
  else:
    records = []
  return [normalize_web_signal_record(record) for record in records]


def load_web_signals_from_yaml(path: str) -> list[dict[str, Any]]:
  with Path(path).open(encoding="utf-8") as handle:
    data = yaml.safe_load(handle)
  if isinstance(data, list):
    records = data
  elif isinstance(data, dict) and isinstance(data.get("signals"), list):
    records = data["signals"]
  else:
    records = []
  return [normalize_web_signal_record(record) for record in records]


def load_web_signal_file(path: str) -> list[dict[str, Any]]:
  suffix = Path(path).suffix.lower()
  if suffix == ".csv":
    return load_web_signals_from_csv(path)
  if suffix == ".json":
    return load_web_signals_from_json(path)
  if suffix in {".yaml", ".yml"}:
    return load_web_signals_from_yaml(path)
  raise ValueError(f"Unsupported web signal file type: {suffix}")


def save_demo_web_signal_template(output_dir: str) -> str:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  path = out / "carbon_fiber_web_signals_template.csv"
  fieldnames = [
    "company",
    "signal_date",
    "source_title",
    "source_url",
    "source_name",
    "signal_type",
    "technology_terms",
    "summary",
    "business_signal",
    "confidence",
    "source_note",
  ]
  rows = [
    {
      "company": "TORAY",
      "signal_date": "2025-01-15",
      "source_title": "Carbon fiber prepreg capacity expansion announcement (template)",
      "source_url": "",
      "source_name": "Company IR template",
      "signal_type": "production_expansion",
      "technology_terms": "carbon fiber, prepreg, aerospace",
      "summary": "Template row for manual web signal input.",
      "business_signal": "Capacity expansion candidate for aerospace prepreg",
      "confidence": "0.6",
      "source_note": "template_example_not_real_source",
    },
    {
      "company": "TEIJIN",
      "signal_date": "2024-11-01",
      "source_title": "Partnership on carbon fiber composite materials (template)",
      "source_url": "https://example.com/template/teijin-partnership",
      "source_name": "Press release template",
      "signal_type": "partnership",
      "technology_terms": "carbon fiber, composite, automotive",
      "summary": "Template partnership signal for mapping tests.",
      "business_signal": "Partnership candidate in automotive composites",
      "confidence": "0.55",
      "source_note": "template_example_not_real_source",
    },
  ]
  with path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
  return str(path)
