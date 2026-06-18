"""Persist Web Signal batches to JSON/CSV/Markdown (Phase 23.0)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from tech_cartography.reports.project_export import load_records_csv, save_records_csv
from tech_cartography.web_signals.schema import (
  WebSignal,
  WebSignalBatch,
  apply_validation_rules,
  web_signal_batch_from_dict,
  web_signal_batch_to_dict,
  web_signal_from_dict,
)

SOURCE_POLICY_VERSION = "phase23.0"

SUMMARY_CAUTION = (
  "Web signals are signal candidates, not final conclusions.\n"
  "Human and money signals require source verification.\n"
  "Synthetic demo signal must be clearly labeled.\n"
  "This is not FTO, infringement, or validity analysis."
)

LIST_FIELDS = (
  "related_technology_terms",
  "related_publication_numbers",
  "related_paper_ids",
)


def web_signals_to_dataframe(signals: list[WebSignal]) -> pd.DataFrame:
  rows: list[dict[str, Any]] = []
  for signal in signals:
    row = apply_validation_rules(signal)
    data = {
      "signal_id": row.signal_id,
      "signal_type": row.signal_type,
      "source_title": row.source_title,
      "source_url": row.source_url,
      "source_domain": row.source_domain,
      "source_date": row.source_date or "",
      "collected_at": row.collected_at,
      "query": row.query,
      "raw_snippet": row.raw_snippet,
      "extracted_text": row.extracted_text or "",
      "related_company": row.related_company or "",
      "related_person": row.related_person or "",
      "related_institution": row.related_institution or "",
      "related_project": row.related_project or "",
      "related_technology_terms": "; ".join(row.related_technology_terms),
      "related_publication_numbers": "; ".join(row.related_publication_numbers),
      "related_paper_ids": "; ".join(row.related_paper_ids),
      "confidence": row.confidence,
      "verification_status": row.verification_status,
      "is_synthetic_demo": row.is_synthetic_demo,
      "caveat": row.caveat,
      "next_verification_action": row.next_verification_action,
    }
    rows.append(data)
  return pd.DataFrame(rows)


def render_web_signal_summary_md(batch: WebSignalBatch) -> str:
  lines = [
    "# Web Signal Batch Summary",
    "",
    f"- batch_id: {batch.batch_id}",
    f"- topic: {batch.topic}",
    f"- created_at: {batch.created_at}",
    f"- source_policy_version: {batch.source_policy_version}",
    f"- signal_count: {len(batch.signals)}",
    "",
    "## Important",
    "",
    SUMMARY_CAUTION,
    "",
  ]
  if batch.notes:
    lines.extend(["## Notes", "", batch.notes, ""])

  if batch.query_set:
    lines.append("## Query Set")
    lines.append("")
    for query in batch.query_set:
      lines.append(f"- {query}")
    lines.append("")

  if batch.signals:
    lines.append("## Signals")
    lines.append("")
    for signal in batch.signals:
      row = apply_validation_rules(signal)
      lines.extend(
        [
          f"### {row.signal_id} ({row.signal_type})",
          "",
          f"- title: {row.source_title}",
          f"- source: {row.source_url or '(none)'}",
          f"- domain: {row.source_domain or '(none)'}",
          f"- confidence: {row.confidence}",
          f"- verification_status: {row.verification_status}",
          f"- synthetic_demo: {row.is_synthetic_demo}",
          f"- caveat: {row.caveat}",
          f"- next_verification_action: {row.next_verification_action or '(none)'}",
          "",
        ],
      )
  else:
    lines.extend(["## Signals", "", "_No signals in this batch._", ""])

  return "\n".join(lines)


def save_web_signal_batch(batch: WebSignalBatch, output_dir: Path | str) -> dict[str, Path]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)

  normalized_signals = [apply_validation_rules(signal) for signal in batch.signals]
  normalized_batch = WebSignalBatch(
    batch_id=batch.batch_id,
    topic=batch.topic,
    created_at=batch.created_at,
    query_set=list(batch.query_set),
    signals=normalized_signals,
    source_policy_version=batch.source_policy_version or SOURCE_POLICY_VERSION,
    notes=batch.notes,
  )

  json_path = out / "web_signals.json"
  csv_path = out / "web_signals.csv"
  md_path = out / "web_signal_summary.md"

  json_path.write_text(
    json.dumps(web_signal_batch_to_dict(normalized_batch), indent=2, ensure_ascii=False),
    encoding="utf-8",
  )
  df = web_signals_to_dataframe(normalized_signals)
  if df.empty:
    save_records_csv([], csv_path)
  else:
    save_records_csv(df.to_dict(orient="records"), csv_path)
  md_path.write_text(render_web_signal_summary_md(normalized_batch), encoding="utf-8")

  return {
    "web_signals_json": json_path,
    "web_signals_csv": csv_path,
    "web_signal_summary_md": md_path,
  }


def load_web_signal_batch(path: Path | str) -> WebSignalBatch | None:
  target = Path(path)
  if target.is_dir():
    target = target / "web_signals.json"
  if not target.exists():
    return None
  try:
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
      return None
    return web_signal_batch_from_dict(data)
  except (OSError, json.JSONDecodeError):
    return None


def load_web_signals_csv(path: Path | str) -> list[WebSignal]:
  csv_path = Path(path)
  if not csv_path.exists():
    return []
  rows = load_records_csv(csv_path)
  signals: list[WebSignal] = []
  for row in rows:
    payload = dict(row)
    for field_name in LIST_FIELDS:
      raw = str(payload.get(field_name) or "").strip()
      payload[field_name] = [part.strip() for part in raw.split(";") if part.strip()] if raw else []
    payload["is_synthetic_demo"] = str(payload.get("is_synthetic_demo", "")).lower() in {"1", "true", "yes"}
    signals.append(web_signal_from_dict(payload))
  return signals
