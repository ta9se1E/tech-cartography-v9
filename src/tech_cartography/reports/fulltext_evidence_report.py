"""Full text evidence collection report."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_fulltext_evidence_summary(result: dict[str, Any]) -> dict[str, Any]:
  retrieved = result.get("retrieved_records", [])
  manual = result.get("manual_required_records", [])
  return {
    "total_candidates": result.get("total_candidates", 0),
    "us_fulltext_candidates": result.get("us_fulltext_candidates", 0),
    "manual_required_candidates": result.get("manual_required_candidates", 0),
    "cache_hits": result.get("cache_hits", 0),
    "retrieved_records": len(retrieved),
    "blocked_by_cost_guard": result.get("blocked_by_cost_guard", 0),
    "total_estimated_gb": result.get("total_estimated_gb", 0.0),
    "total_estimated_usd": result.get("total_estimated_usd", 0.0),
    "maximum_bytes_billed_gb": result.get("maximum_bytes_billed_gb", 0.0),
    "retrieved": retrieved,
    "manual_required": manual,
    "mode": result.get("mode"),
    "next_phases": [
      "Claim Element Extraction",
      "OpenAlex Paper Evidence",
      "SourceQualityAgent",
    ],
  }


def render_fulltext_evidence_markdown(summary: dict[str, Any]) -> str:
  lines = [
    "# Top5 Full Text Evidence Collection",
    "",
    "## 1. Summary",
    "",
    f"- total candidates: {summary.get('total_candidates', 0)}",
    f"- US full text candidates: {summary.get('us_fulltext_candidates', 0)}",
    f"- manual required candidates: {summary.get('manual_required_candidates', 0)}",
    f"- cache hits: {summary.get('cache_hits', 0)}",
    f"- retrieved records: {summary.get('retrieved_records', 0)}",
    f"- blocked by cost guard: {summary.get('blocked_by_cost_guard', 0)}",
    "",
    "## 2. Retrieved Full Text Records",
    "",
  ]
  for record in summary.get("retrieved", []):
    coverage = record.get("evidence_coverage", {})
    lines.extend(
      [
        f"### {record.get('publication_number')}",
        f"- title: {record.get('title')}",
        f"- assignee: {record.get('assignee')}",
        f"- route: {record.get('source_route')}",
        f"- evidence_level: {record.get('evidence_level')}",
        f"- has_claims: {coverage.get('has_claims')}",
        f"- has_independent_claim: {coverage.get('has_independent_claim')}",
        f"- has_description: {coverage.get('has_description')}",
        f"- has_examples: {coverage.get('has_examples')}",
        f"- has_measured_properties: {coverage.get('has_measured_properties')}",
        f"- next_step: {record.get('retrieval_status')}",
        "",
      ],
    )

  lines.extend(["## 3. Manual Full Text Required", ""])
  for record in summary.get("manual_required", []):
    lines.extend(
      [
        f"- {record.get('publication_number')} | {record.get('title')} | {record.get('country')}",
        f"  - reason: non-US or BigQuery full text unavailable",
        f"  - recommended manual action: upload TXT/MD/CSV/XLSX full text",
      ],
    )

  lines.extend(
    [
      "",
      "## 4. Cost Guard / Dry Run",
      "",
      f"- estimated GB: {summary.get('total_estimated_gb', 0.0):.4f}",
      f"- estimated USD: {summary.get('total_estimated_usd', 0.0):.4f}",
      f"- maximum GB: {summary.get('maximum_bytes_billed_gb', 0.0)}",
      f"- mode: {summary.get('mode')}",
      "",
      "## 5. Next Phase",
      "",
    ],
  )
  for step in summary.get("next_phases", []):
    lines.append(f"- {step}")
  return "\n".join(lines)


def save_fulltext_evidence_report(markdown: str, output_dir: str) -> str:
  path = Path(output_dir) / "fulltext_evidence_report.md"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(markdown, encoding="utf-8")
  return str(path)
