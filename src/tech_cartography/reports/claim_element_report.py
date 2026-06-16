"""Claim element extraction report."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from tech_cartography.domain.claim_element import ClaimElement


def build_claim_element_summary(result: dict[str, Any]) -> dict[str, Any]:
  elements = [
    item if isinstance(item, ClaimElement) else ClaimElement.from_dict(item)
    for item in result.get("elements", [])
  ]
  support_counter = Counter(element.support_status for element in elements)
  type_counter = Counter(element.element_type for element in elements)
  return {
    "total_records": result.get("total_records", 0),
    "records_with_claims": result.get("records_with_claims", 0),
    "records_without_claims": result.get("total_records", 0) - result.get("records_with_claims", 0),
    "total_claim_elements": len(elements),
    "high_confidence_elements": sum(1 for element in elements if element.confidence >= 0.7),
    "claim_only_elements": support_counter.get("claim_only", 0),
    "supported_by_examples_elements": support_counter.get("supported_by_examples", 0),
    "generated_paper_queries": len(result.get("paper_queries", [])),
    "record_results": result.get("record_results", []),
    "elements": [element.to_dict() for element in elements],
    "paper_queries": result.get("paper_queries", []),
    "support_status_counts": dict(support_counter),
    "element_type_counts": dict(type_counter),
    "next_phases": [
      "OpenAlex Paper Evidence Search",
      "SourceQualityAgent",
      "Patent Claim × Paper Evidence Map",
    ],
  }


def render_claim_element_markdown(summary: dict[str, Any]) -> str:
  lines = [
    "# Claim Element Extraction Report",
    "",
    "## 1. Summary",
    "",
    f"- total records: {summary.get('total_records', 0)}",
    f"- records with claims: {summary.get('records_with_claims', 0)}",
    f"- records without claims: {summary.get('records_without_claims', 0)}",
    f"- total claim elements: {summary.get('total_claim_elements', 0)}",
    f"- high confidence elements: {summary.get('high_confidence_elements', 0)}",
    f"- claim_only elements: {summary.get('claim_only_elements', 0)}",
    f"- supported_by_examples elements: {summary.get('supported_by_examples_elements', 0)}",
    f"- generated paper queries: {summary.get('generated_paper_queries', 0)}",
    "",
    "## 2. Records",
    "",
  ]
  for record in summary.get("record_results", []):
    elements = record.get("elements", [])
    lines.extend(
      [
        f"### {record.get('publication_number')}",
        f"- title: {record.get('title')}",
        f"- evidence_level: {record.get('evidence_level')}",
        f"- extraction_status: {record.get('extraction_status')}",
        f"- element count: {len(elements)}",
        "",
      ],
    )

  lines.extend(["## 3. Claim Elements by Type", ""])
  for element_type, count in sorted(summary.get("element_type_counts", {}).items()):
    lines.append(f"- {element_type}: {count}")

  lines.extend(["", "## 4. Support Status", ""])
  for status, count in sorted(summary.get("support_status_counts", {}).items()):
    lines.append(f"- {status}: {count}")

  lines.extend(["", "## 5. Paper Query Candidates", ""])
  for query in summary.get("paper_queries", [])[:20]:
    lines.append(
      f"- [{query.get('priority')}] {query.get('query')} "
      f"({query.get('publication_number')} / {query.get('element_type')})",
    )

  lines.extend(["", "## 6. Next Phase", ""])
  for step in summary.get("next_phases", []):
    lines.append(f"- {step}")
  return "\n".join(lines)


def save_claim_element_report(markdown: str, output_dir: str) -> str:
  path = Path(output_dir) / "claim_element_report.md"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(markdown, encoding="utf-8")
  return str(path)
