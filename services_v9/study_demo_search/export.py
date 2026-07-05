"""Export helpers for study demo search results."""

from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Any, Mapping, Sequence

RELEVANCE_EXPORT_FIELDS = (
  "relevance_tier",
  "relevance_score",
  "relevance_reason",
  "source_raw_score",
  "source_normalized_score",
  "integrated_relevance_score",
  "matched_core_terms",
  "matched_material_terms",
  "matched_process_terms",
  "matched_property_terms",
  "matched_negative_terms",
  "target_material_match",
  "target_material_mismatch",
  "score_breakdown",
)


def build_export_bundle(
  signals: Sequence[Mapping[str, Any]],
  keywords: Mapping[str, Any],
  similar: Mapping[str, Any],
  usage: Mapping[str, Any],
  *,
  filtered_signals: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
  all_signals = list(signals)
  visible_signals = list(filtered_signals) if filtered_signals is not None else all_signals
  return {
    "patent_csv": _to_csv([item for item in visible_signals if item.get("source_type") == "patent"]),
    "paper_csv": _to_csv([item for item in visible_signals if item.get("source_type") == "paper"]),
    "web_csv": _to_csv([item for item in visible_signals if item.get("source_type") == "web_company"]),
    "integrated_csv": _to_csv(visible_signals),
    "integrated_csv_all_tiers": _to_csv(all_signals),
    "integrated_markdown": _to_markdown(all_signals),
    "integrated_markdown_filtered": _to_markdown(visible_signals),
    "all_results_json": json.dumps({"signals": all_signals}, ensure_ascii=False, indent=2),
    "filtered_results_json": json.dumps({"signals": visible_signals}, ensure_ascii=False, indent=2),
    "usage_metrics_json": json.dumps(dict(usage), ensure_ascii=False, indent=2),
    "keyword_suggestions_json": json.dumps(dict(keywords), ensure_ascii=False, indent=2),
    "similar_patents_json": json.dumps(dict(similar), ensure_ascii=False, indent=2),
  }


def _serialize_value(value: Any) -> Any:
  if isinstance(value, (list, dict)):
    return json.dumps(value, ensure_ascii=False)
  return value


def _to_csv(rows: Sequence[Mapping[str, Any]]) -> str:
  if not rows:
    return ""
  fieldnames = sorted({key for row in rows for key in row.keys()} | set(RELEVANCE_EXPORT_FIELDS))
  buffer = StringIO()
  writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
  writer.writeheader()
  for row in rows:
    writer.writerow({key: _serialize_value(row.get(key, "")) for key in fieldnames})
  return buffer.getvalue()


def _to_markdown(rows: Sequence[Mapping[str, Any]]) -> str:
  lines = ["# Integrated Signals Export", ""]
  for index, row in enumerate(rows, start=1):
    lines.extend(
      [
        f"## {index}. {row.get('title', '')}",
        "",
        f"- relevance_tier: `{row.get('relevance_tier', '')}`",
        f"- relevance_score: `{row.get('relevance_score', '')}`",
        f"- relevance_reason: {row.get('relevance_reason', '')}",
        f"- source_type: `{row.get('source_type', '')}`",
        f"- target_material_match: `{row.get('target_material_match', '')}`",
        f"- target_material_mismatch: `{row.get('target_material_mismatch', '')}`",
        f"- matched_core_terms: `{row.get('matched_core_terms', [])}`",
        f"- matched_negative_terms: `{row.get('matched_negative_terms', [])}`",
        f"- score_breakdown: `{row.get('score_breakdown', {})}`",
        f"- url: {row.get('url', '')}",
        "",
      ]
    )
  return "\n".join(lines) + "\n"
