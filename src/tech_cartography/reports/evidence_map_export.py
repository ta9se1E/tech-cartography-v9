"""Export helpers for claim-paper evidence map outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tech_cartography.reports.claim_paper_evidence_map_report import (
  build_claim_paper_evidence_map_summary,
  render_claim_paper_evidence_map_markdown,
  save_claim_paper_evidence_map_report,
)
from tech_cartography.reports.project_export import save_records_csv


def save_claim_paper_evidence_map_outputs(
  result: dict[str, Any],
  output_dir: str | Path,
  top_n: int = 30,
) -> dict[str, str]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  summary = build_claim_paper_evidence_map_summary(result)
  markdown = render_claim_paper_evidence_map_markdown(summary)
  top_items = result.get("top_evidence_items", [])[:top_n]

  paths = {
    "claim_paper_evidence_items_csv": save_records_csv(
      result.get("evidence_items", []),
      out / "claim_paper_evidence_items.csv",
    ),
    "evidence_by_element_type_csv": save_records_csv(
      result.get("evidence_by_element_type", []),
      out / "evidence_by_element_type.csv",
    ),
    "evidence_gaps_csv": save_records_csv(
      result.get("evidence_gaps", []),
      out / "evidence_gaps.csv",
    ),
    "top_evidence_items_csv": save_records_csv(top_items, out / "top_evidence_items.csv"),
    "patent_evidence_maps_json": str(out / "patent_evidence_maps.json"),
    "claim_paper_evidence_map_summary_json": str(out / "claim_paper_evidence_map_summary.json"),
    "claim_paper_evidence_map_report_md": save_claim_paper_evidence_map_report(markdown, out),
  }

  with Path(paths["patent_evidence_maps_json"]).open("w", encoding="utf-8") as handle:
    json.dump(result.get("patent_evidence_maps", []), handle, indent=2, ensure_ascii=False)

  with Path(paths["claim_paper_evidence_map_summary_json"]).open("w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2, ensure_ascii=False)

  paths["output_dir"] = str(out)
  return paths
