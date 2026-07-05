"""Export helpers for study demo search results."""

from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Any, Mapping, Sequence


def build_export_bundle(
  signals: Sequence[Mapping[str, Any]],
  keywords: Mapping[str, Any],
  similar: Mapping[str, Any],
  usage: Mapping[str, Any],
) -> dict[str, Any]:
  return {
    "patent_csv": _to_csv([item for item in signals if item.get("source_type") == "patent"]),
    "paper_csv": _to_csv([item for item in signals if item.get("source_type") == "paper"]),
    "web_csv": _to_csv([item for item in signals if item.get("source_type") == "web_company"]),
    "integrated_csv": _to_csv(signals),
    "all_results_json": json.dumps({"signals": list(signals)}, ensure_ascii=False, indent=2),
    "usage_metrics_json": json.dumps(dict(usage), ensure_ascii=False, indent=2),
    "keyword_suggestions_json": json.dumps(dict(keywords), ensure_ascii=False, indent=2),
    "similar_patents_json": json.dumps(dict(similar), ensure_ascii=False, indent=2),
  }


def _to_csv(rows: Sequence[Mapping[str, Any]]) -> str:
  if not rows:
    return ""
  fieldnames = sorted({key for row in rows for key in row.keys()})
  buffer = StringIO()
  writer = csv.DictWriter(buffer, fieldnames=fieldnames)
  writer.writeheader()
  for row in rows:
    writer.writerow({key: row.get(key, "") for key in fieldnames})
  return buffer.getvalue()
