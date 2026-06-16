"""Paper evidence report generation."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any


def build_paper_evidence_summary(result: dict[str, Any]) -> dict[str, Any]:
  evidence_links = list(result.get("evidence_links", []))
  source_quality_results = list(result.get("source_quality_results", []))
  relation_counter = Counter(link.get("evidence_relation") for link in evidence_links)
  quality_counter = Counter(item.get("quality_level") for item in source_quality_results)
  do_not_cite = [
    item for item in source_quality_results if item.get("recommended_use") == "do_not_cite"
  ]
  return {
    "query_candidates": result.get("total_query_candidates", 0),
    "executed_queries": result.get("executed_queries", 0),
    "cache_hits": result.get("cache_hits", 0),
    "papers_raw": result.get("total_papers_raw", 0),
    "papers_dedup": result.get("total_papers_dedup", 0),
    "evidence_links": len(evidence_links),
    "high_quality_sources": quality_counter.get("high", 0),
    "supporting_evidence_candidates": relation_counter.get("supporting_evidence_candidate", 0),
    "background_evidence": relation_counter.get("background_evidence", 0),
    "weak_matches": relation_counter.get("weak_match", 0),
    "mode": result.get("mode"),
    "warnings": result.get("warnings", []),
    "errors": result.get("errors", []),
    "evidence_by_patent": result.get("evidence_by_patent", []),
    "evidence_links_detail": evidence_links,
    "source_quality_results": source_quality_results,
    "source_quality_counts": dict(quality_counter),
    "do_not_cite_candidates": do_not_cite,
    "next_phases": [
      "Patent Claim × Paper Evidence Map",
      "Technical View Agent",
      "Business View Agent",
      "Synthesis Report",
    ],
  }


def render_paper_evidence_markdown(summary: dict[str, Any]) -> str:
  lines = [
    "# OpenAlex Paper Evidence Report",
    "",
    "## 1. Summary",
    "",
    f"- query candidates: {summary.get('query_candidates', 0)}",
    f"- executed queries: {summary.get('executed_queries', 0)}",
    f"- cache hits: {summary.get('cache_hits', 0)}",
    f"- papers raw: {summary.get('papers_raw', 0)}",
    f"- papers dedup: {summary.get('papers_dedup', 0)}",
    f"- evidence links: {summary.get('evidence_links', 0)}",
    f"- high quality sources: {summary.get('high_quality_sources', 0)}",
    f"- supporting evidence candidates: {summary.get('supporting_evidence_candidates', 0)}",
    f"- background evidence: {summary.get('background_evidence', 0)}",
    "",
    "## 2. Paper Evidence by Patent",
    "",
  ]
  for record in summary.get("evidence_by_patent", []):
    lines.extend(
      [
        f"### {record.get('publication_number')}",
        f"- linked papers count: {record.get('linked_papers_count', 0)}",
        f"- claim elements linked: {record.get('claim_elements_linked', 0)}",
        f"- supporting evidence candidates: {record.get('supporting_evidence_candidates', 0)}",
        f"- background evidence: {record.get('background_evidence', 0)}",
        f"- weak matches: {record.get('weak_matches', 0)}",
        "",
      ],
    )
    for paper in record.get("top_linked_papers", [])[:3]:
      lines.append(
        f"  - {paper.get('paper_title')} "
        f"({paper.get('evidence_relation')}, score={paper.get('relevance_score')})",
      )
    lines.append("")

  lines.extend(["## 3. Claim Element × Paper Links", ""])
  for link in summary.get("evidence_links_detail", [])[:25]:
    lines.append(
      f"- {link.get('element_text')} → {link.get('paper_title')} "
      f"[{link.get('evidence_relation')}, relevance={link.get('relevance_score')}, "
      f"quality={link.get('source_quality_level')}] "
      f"{link.get('display_url') or ''}",
    )

  lines.extend(["", "## 4. Source Quality", ""])
  for level, count in sorted(summary.get("source_quality_counts", {}).items()):
    lines.append(f"- {level}: {count}")
  if summary.get("do_not_cite_candidates"):
    lines.append("")
    lines.append("do_not_cite candidates:")
    for item in summary["do_not_cite_candidates"][:10]:
      lines.append(f"- {item.get('source_id')} ({item.get('quality_level')})")

  lines.extend(
    [
      "",
      "## 5. Caveats",
      "",
      "- OpenAlex検索は候補探索であり、論文が特許主張を直接証明するわけではない",
      "- abstract不足や表記揺れにより取りこぼしがある",
      "- 次フェーズでClaim × Paper Evidence Mapとして人間が確認しやすい形に整理する",
      "",
      "## 6. Next Phase",
      "",
    ],
  )
  for step in summary.get("next_phases", []):
    lines.append(f"- {step}")
  return "\n".join(lines)


def save_paper_evidence_report(markdown: str, output_dir: str | Path) -> str:
  path = Path(output_dir) / "paper_evidence_report.md"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(markdown, encoding="utf-8")
  return str(path)
