"""Export helpers for web signal mapping outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tech_cartography.evidence.web_signal_mapper import map_web_signals_to_patents
from tech_cartography.ingestion.web_signal_loader import load_web_signal_file
from tech_cartography.reports.project_export import save_records_csv
from tech_cartography.reports.web_signal_report import (
  build_web_signal_summary,
  render_web_signal_markdown,
  save_web_signal_report,
)


def run_web_signal_mapping(
  signals: list[dict[str, Any]],
  patents: list[dict[str, Any]],
) -> dict[str, Any]:
  return map_web_signals_to_patents(signals, patents)


def save_web_signal_outputs(result: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  summary = build_web_signal_summary(result)
  markdown = render_web_signal_markdown(summary)

  paths = {
    "normalized_web_signals_csv": save_records_csv(
      result.get("normalized_signals", []),
      out / "normalized_web_signals.csv",
    ),
    "web_signal_quality_results_csv": save_records_csv(
      result.get("quality_results", []),
      out / "web_signal_quality_results.csv",
    ),
    "web_signal_patent_links_csv": save_records_csv(
      result.get("links", []),
      out / "web_signal_patent_links.csv",
    ),
    "web_signals_by_company_csv": save_records_csv(
      result.get("by_company", []),
      out / "web_signals_by_company.csv",
    ),
    "web_signals_by_cluster_csv": save_records_csv(
      result.get("by_cluster", []),
      out / "web_signals_by_cluster.csv",
    ),
    "web_signals_by_patent_json": str(out / "web_signals_by_patent.json"),
    "web_signal_report_md": save_web_signal_report(markdown, out),
  }
  with Path(paths["web_signals_by_patent_json"]).open("w", encoding="utf-8") as handle:
    json.dump(result.get("by_patent", []), handle, indent=2, ensure_ascii=False)
  paths["output_dir"] = str(out)
  return paths


def load_signals_and_patents(
  web_signal_file: str,
  patents_csv_loader,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
  signals = load_web_signal_file(web_signal_file)
  patents = patents_csv_loader()
  return signals, patents
