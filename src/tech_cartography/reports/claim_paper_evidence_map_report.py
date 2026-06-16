"""Claim × Paper Evidence Map report generation."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from tech_cartography.evidence.evidence_gap_analyzer import summarize_gaps_by_patent


def build_claim_paper_evidence_map_summary(result: dict[str, Any]) -> dict[str, Any]:
  evidence_items = list(result.get("evidence_items", []))
  relation_counter = Counter(item.get("evidence_relation") for item in evidence_items)
  quality_counter = Counter(
    item.get("source_quality_level")
    for item in evidence_items
    if item.get("source_quality_level")
  )
  return {
    "total_patents": result.get("total_patents", 0),
    "total_claim_elements": result.get("total_claim_elements", 0),
    "total_evidence_items": result.get("total_evidence_items", 0),
    "supporting_evidence_candidates": result.get("supporting_evidence_candidates", 0)
    + result.get("strong_evidence_candidates", 0),
    "background_evidence": result.get("background_evidence_items", 0),
    "weak_matches": result.get("weak_matches", 0),
    "no_paper_evidence": result.get("no_paper_evidence_items", 0),
    "high_quality_sources": quality_counter.get("high", 0),
    "relation_counts": dict(relation_counter),
    "quality_counts": dict(quality_counter),
    "patent_evidence_maps": result.get("patent_evidence_maps", []),
    "evidence_items": evidence_items,
    "evidence_by_element_type": result.get("evidence_by_element_type", []),
    "top_evidence_items": result.get("top_evidence_items", []),
    "evidence_gaps": result.get("evidence_gaps", []),
    "gaps_by_patent": summarize_gaps_by_patent(result.get("evidence_gaps", [])),
    "warnings": result.get("warnings", []),
    "errors": result.get("errors", []),
    "next_phases": [
      "Technical View Agent",
      "Business View Agent",
      "Synthesis Report",
      "Web / Company Signal Mapping",
    ],
  }


def render_claim_paper_evidence_map_markdown(summary: dict[str, Any]) -> str:
  lines = [
    "# Patent Claim × Paper Evidence Map",
    "",
    "## 1. Summary",
    "",
    f"- patents: {summary.get('total_patents', 0)}",
    f"- claim elements: {summary.get('total_claim_elements', 0)}",
    f"- evidence items: {summary.get('total_evidence_items', 0)}",
    f"- supporting evidence candidates: {summary.get('supporting_evidence_candidates', 0)}",
    f"- background evidence: {summary.get('background_evidence', 0)}",
    f"- weak matches: {summary.get('weak_matches', 0)}",
    f"- no paper evidence: {summary.get('no_paper_evidence', 0)}",
    f"- high quality sources: {summary.get('high_quality_sources', 0)}",
    "",
    "## 2. Patent-level Evidence Maps",
    "",
  ]

  for patent_map in summary.get("patent_evidence_maps", []):
    lines.extend(
      [
        f"### {patent_map.get('publication_number')}",
        f"- title: {patent_map.get('patent_title')}",
        f"- assignee: {patent_map.get('assignee')}",
        f"- evidence_level: {patent_map.get('evidence_level')}",
        f"- claim elements count: {patent_map.get('total_claim_elements', 0)}",
        f"- supporting paper candidates: {patent_map.get('elements_with_supporting_papers', 0)}",
        f"- background papers: {patent_map.get('elements_with_background_papers', 0)}",
        f"- evidence gaps: {sum(1 for gap in summary.get('evidence_gaps', []) if gap.get('publication_number') == patent_map.get('publication_number'))}",
        f"- next actions: {', '.join(patent_map.get('next_actions', []))}",
        "",
      ],
    )

  lines.extend(["## 3. Claim Element × Paper Evidence", ""])
  lines.append(
    "| patent | claim element | type | paper | source | relation | confidence | quality | matched terms | caveat |",
  )
  lines.append("|---|---|---|---|---|---|---|---|---|---|")
  for item in summary.get("top_evidence_items", [])[:25]:
    matched = ", ".join(item.get("matched_terms", [])[:4])
    caveat = str(item.get("caveat", ""))[:80].replace("|", "/")
    lines.append(
      f"| {item.get('publication_number')} | {str(item.get('element_text', ''))[:40]} | "
      f"{item.get('element_type')} | {str(item.get('paper_title') or 'N/A')[:40]} | "
      f"{item.get('source_name') or 'N/A'} | {item.get('evidence_relation')} | "
      f"{item.get('evidence_confidence')} | {item.get('source_quality_level')} | "
      f"{matched} | {caveat} |",
    )

  lines.extend(["", "## 4. Evidence by Element Type", ""])
  for row in summary.get("evidence_by_element_type", []):
    lines.append(
      f"- {row.get('element_type')}: items={row.get('item_count')}, "
      f"supporting={row.get('supporting_candidates')}, background={row.get('background_evidence')}, "
      f"weak={row.get('weak_matches')}, no_paper={row.get('no_paper_evidence')}",
    )

  lines.extend(["", "## 5. Evidence Gaps", ""])
  gap_types = Counter(gap.get("gap_type") for gap in summary.get("evidence_gaps", []))
  for gap_type, count in sorted(gap_types.items()):
    lines.append(f"- {gap_type}: {count}")
  for gap in summary.get("evidence_gaps", [])[:15]:
    lines.append(
      f"  - {gap.get('publication_number')} / {gap.get('element_id')}: "
      f"{gap.get('gap_type')} → {gap.get('recommended_action')}",
    )

  lines.extend(
    [
      "",
      "## 6. Caveats",
      "",
      "- OpenAlex論文は技術主張の裏取り候補であり、特許主張を証明するものではない",
      "- SourceQualityは参照元としての扱いやすさを評価するものであり、論文内容の正しさを保証しない",
      "- ClaimElement抽出はルールベースであり、人間確認が必要",
      "- abstract不足、表記ゆれ、検索語不足により取りこぼしがある",
      "",
      "## 7. Next Phase",
      "",
    ],
  )
  for step in summary.get("next_phases", []):
    lines.append(f"- {step}")
  return "\n".join(lines)


def save_claim_paper_evidence_map_report(markdown: str, output_dir: str | Path) -> str:
  path = Path(output_dir) / "claim_paper_evidence_map_report.md"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(markdown, encoding="utf-8")
  return str(path)
