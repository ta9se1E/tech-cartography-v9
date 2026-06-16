"""Full text evidence collection report."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_fulltext_evidence_summary(result: dict[str, Any]) -> dict[str, Any]:
  retrieved = result.get("retrieved_records", [])
  manual = result.get("manual_required_records", [])
  plan = result.get("plan", {})
  plan_summary = plan.get("plan_summary", {})
  strategic_rows = result.get("strategic_watch_manual_rows", [])

  return {
    "total_candidates": result.get("total_top5_candidates", result.get("total_candidates", 0)),
    "total_top5_candidates": result.get("total_top5_candidates", result.get("total_candidates", 0)),
    "us_fulltext_targets": result.get("us_fulltext_targets", result.get("us_fulltext_candidates", 0)),
    "us_fulltext_candidates": result.get("us_fulltext_candidates", 0),
    "manual_required_candidates": result.get("manual_required_candidates", len(manual)),
    "manual_required_count": result.get("manual_required_count", 0),
    "strategic_watch_manual_count": result.get("strategic_watch_manual_count", len(strategic_rows)),
    "cn_watch_count": plan_summary.get("cn_watch_count", 0),
    "cache_hits": result.get("cache_hit_count", result.get("cache_hits", 0)),
    "cache_hit_count": result.get("cache_hit_count", result.get("cache_hits", 0)),
    "retrieved_count": result.get("retrieved_count", 0),
    "dry_run_only_count": result.get("dry_run_only_count", 0),
    "skipped_not_selected_count": result.get("skipped_not_selected_count", 0),
    "execute_selected_count": result.get("execute_selected_count", 0),
    "execute_requested": result.get("execute_requested", False),
    "confirm_fulltext_execute": result.get("confirm_fulltext_execute", False),
    "execute_limit": result.get("execute_limit"),
    "publication_number_filter": result.get("publication_number_filter"),
    "retrieved_records": len(retrieved),
    "blocked_by_cost_guard": result.get("blocked_by_cost_guard", 0),
    "cost_guard_status": result.get("cost_guard_status", "ok"),
    "high_fulltext_evidence_count": result.get("high_fulltext_evidence_count", 0),
    "medium_fulltext_evidence_count": result.get("medium_fulltext_evidence_count", 0),
    "low_fulltext_evidence_count": result.get("low_fulltext_evidence_count", 0),
    "metadata_only_count": result.get("metadata_only_count", 0),
    "total_estimated_gb": result.get("total_estimated_gb", 0.0),
    "total_estimated_usd": result.get("total_estimated_usd", 0.0),
    "maximum_bytes_billed_gb": result.get("maximum_bytes_billed_gb", 0.0),
    "retrieved": retrieved,
    "manual_required": manual,
    "manual_required_rows": result.get("manual_required_rows", []),
    "strategic_watch_manual_rows": strategic_rows,
    "plan_summary": plan_summary,
    "mode": result.get("mode"),
    "warnings": result.get("warnings", []),
    "errors": result.get("errors", []),
    "next_phases": [
      "Manual PDF check for Strategic Watch candidates",
      "Claim Element Extraction",
      "OpenAlex Paper Evidence",
      "SourceQualityAgent",
    ],
  }


def render_fulltext_evidence_markdown(summary: dict[str, Any]) -> str:
  lines = [
    "# Controlled Full Text Run — Top5 Evidence Collection",
    "",
    "## Controlled Full Text Run Summary",
    "",
    f"- total Top5 candidates: {summary.get('total_top5_candidates', 0)}",
    f"- US fulltext targets: {summary.get('us_fulltext_targets', 0)}",
    f"- retrieved: {summary.get('retrieved_count', 0)}",
    f"- dry run only: {summary.get('dry_run_only_count', 0)}",
    f"- cache hits: {summary.get('cache_hit_count', 0)}",
    f"- manual required: {summary.get('manual_required_count', 0)}",
    f"- strategic watch manual: {summary.get('strategic_watch_manual_count', 0)}",
    f"- CN watch count: {summary.get('cn_watch_count', 0)}",
    f"- cost guard: {summary.get('cost_guard_status', 'ok')}",
    f"- mode: {summary.get('mode')}",
    f"- execute requested: {summary.get('execute_requested', False)}",
    f"- confirm fulltext execute: {summary.get('confirm_fulltext_execute', False)}",
    f"- execute limit: {summary.get('execute_limit')}",
    f"- execute selected: {summary.get('execute_selected_count', 0)}",
    f"- skipped not selected: {summary.get('skipped_not_selected_count', 0)}",
    "",
    "## US Full Text Retrieval Targets",
    "",
  ]
  for record in summary.get("retrieved", []):
    if str(record.get("country", "US")).upper() != "US" and record.get("source_route") != "us_bigquery_fulltext_candidate":
      continue
    lines.append(
      f"- {record.get('publication_number')} | {record.get('title')} | status={record.get('retrieval_status')}",
    )

  lines.extend(["", "## Retrieved / Dry Run / Cache Hit", ""])
  for record in summary.get("retrieved", []):
    coverage = record.get("evidence_coverage", {})
    lines.extend(
      [
        f"### {record.get('publication_number')}",
        f"- title: {record.get('title')}",
        f"- assignee: {record.get('assignee')}",
        f"- route: {record.get('source_route')}",
        f"- retrieval_status: {record.get('retrieval_status')}",
        f"- evidence_level: {record.get('evidence_level')}",
        f"- claims_source: {record.get('claims_source')}",
        f"- description_source: {record.get('description_source')}",
        f"- has_claims: {coverage.get('has_claims')}",
        f"- has_description: {coverage.get('has_description')}",
        f"- has_examples: {coverage.get('has_examples')}",
        f"- has_measured_properties: {coverage.get('has_measured_properties')}",
        "",
      ],
    )

  lines.extend(["", "## Manual Full Text Required", ""])
  for record in summary.get("manual_required_rows", []):
    lines.append(
      f"- {record.get('publication_number')} | {record.get('country')} | {record.get('assignee')}",
    )

  lines.extend(["", "## China / Non-US Strategic Watch Manual Checks", ""])
  for record in summary.get("strategic_watch_manual_rows", [])[:25]:
    lines.extend(
      [
        f"- {record.get('publication_number')} | {record.get('country')} | {record.get('assignee')}",
        f"  - {record.get('watch_reason_japanese', record.get('manual_route_reason', ''))}",
      ],
    )

  lines.extend(
    [
      "",
      "## Evidence Coverage",
      "",
      f"- high: {summary.get('high_fulltext_evidence_count', 0)}",
      f"- medium: {summary.get('medium_fulltext_evidence_count', 0)}",
      f"- low: {summary.get('low_fulltext_evidence_count', 0)}",
      f"- metadata_only: {summary.get('metadata_only_count', 0)}",
      "",
      "## Caveats",
      "",
      "- US fulltext取得は技術重要度ランキングではありません",
      "- CN/EP/JP等はmanual routeで別管理します",
      "- claims/descriptionが取れないことは、その特許が重要でないことを意味しません",
      "- 特許の有効性/FTOは判断しません",
      "",
      "## Cost Guard / Dry Run",
      "",
      f"- estimated GB: {summary.get('total_estimated_gb', 0.0):.4f}",
      f"- estimated USD: {summary.get('total_estimated_usd', 0.0):.4f}",
      f"- maximum GB: {summary.get('maximum_bytes_billed_gb', 0.0)}",
      "",
      "## Next Phase",
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
