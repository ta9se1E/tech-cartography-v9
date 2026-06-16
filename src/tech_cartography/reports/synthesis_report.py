"""Synthesis report rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_synthesis_report_summary(result: dict[str, Any]) -> dict[str, Any]:
  return {
    "report_title": result.get("report_title", "Carbon Fiber Evidence Map v1"),
    "theme": result.get("theme"),
    "generated_at": result.get("generated_at"),
    "executive_summary": result.get("executive_summary"),
    "key_findings": result.get("key_findings", []),
    "priority_patents": result.get("priority_patents", []),
    "technology_cluster_summary": result.get("technology_cluster_summary", []),
    "evidence_strength_summary": result.get("evidence_strength_summary", {}),
    "technical_view_summary": result.get("technical_view_summary", {}),
    "business_view_summary": result.get("business_view_summary", {}),
    "sme_action_plan": result.get("sme_action_plan", []),
    "evidence_gaps": result.get("evidence_gaps", []),
    "next_update_recommendations": result.get("next_update_recommendations", []),
    "caveats": result.get("caveats", []),
    "web_signals_by_company": result.get("web_signals_by_company", []),
    "web_signals_by_cluster": result.get("web_signals_by_cluster", []),
    "claim_paper_summary": result.get("claim_paper_summary", {}),
  }


def render_synthesis_markdown(summary: dict[str, Any]) -> str:
  lines = [
    f"# {summary.get('report_title', 'Carbon Fiber Evidence Map v1')}",
    "",
    f"- theme: {summary.get('theme')}",
    f"- generated_at: {summary.get('generated_at')}",
    "",
    "## 1. Executive Summary",
    "",
    summary.get("executive_summary", ""),
    "",
    "## 2. What This Report Does",
    "",
    "- 特許検索（BigQuery light multi-query retrieval）",
    "- 技術分類（technology clustering）",
    "- Top特許抽出（Top20 / Top5 fulltext候補）",
    "- claims / description取得（full text evidence collection）",
    "- claim element分解",
    "- 論文Evidence Candidate探索（OpenAlex）",
    "- Patent Claim × Paper Evidence Map",
    "- Web/企業シグナル対応",
    "- 技術評価（Technical View Agent）",
    "- 事業評価（Business View Agent）",
    "",
    "## 3. Key Findings",
    "",
  ]

  for finding in summary.get("key_findings", []):
    lines.extend(
      [
        f"### {finding.get('finding_id')}: {finding.get('title')}",
        f"- type: {finding.get('finding_type')}",
        f"- summary: {finding.get('summary')}",
        f"- importance: {finding.get('importance')}",
        f"- confidence: {finding.get('confidence')}",
        f"- related patents: {', '.join(finding.get('related_publications', []))}",
        f"- related companies: {', '.join(finding.get('related_companies', []))}",
        f"- evidence basis: {', '.join(finding.get('evidence_basis', []))}",
        f"- caveat: {', '.join(finding.get('caveats', []))}",
        f"- recommended next action: {finding.get('recommended_next_action')}",
        "",
      ],
    )

  lines.extend(["## 4. Technology Cluster Map", ""])
  for cluster in summary.get("technology_cluster_summary", []):
    lines.extend(
      [
        f"### {cluster.get('name')} ({cluster.get('cluster_id')})",
        f"- patent count: {cluster.get('patent_count')}",
        f"- categories: {', '.join(cluster.get('categories', []))}",
        f"- representative patents: {', '.join(cluster.get('representative_patents', []))}",
        f"- technical signal: {cluster.get('technical_signal')}",
        f"- business signal: {cluster.get('business_signal')}",
        f"- evidence gaps: {cluster.get('evidence_gaps')}",
        f"- next action: {cluster.get('next_action')}",
        "",
      ],
    )

  lines.extend(["## 5. Priority Patents to Read", ""])
  for patent in summary.get("priority_patents", []):
    lines.extend(
      [
        f"### {patent.get('publication_number')}",
        f"- title: {patent.get('title')}",
        f"- assignee: {patent.get('assignee')}",
        f"- cluster: {patent.get('primary_cluster_name') or patent.get('primary_cluster_id')}",
        f"- technical confidence: {patent.get('technical_confidence')}",
        f"- business confidence: {patent.get('business_confidence')}",
        f"- why read: {patent.get('why_read')}",
        f"- next check: {patent.get('next_check')}",
        "",
      ],
    )

  evidence = summary.get("evidence_strength_summary", {})
  claim_paper = summary.get("claim_paper_summary", {})
  lines.extend(
    [
      "## 6. Patent Claim × Paper Evidence Highlights",
      "",
      f"- supporting evidence candidates: {evidence.get('supporting_evidence_candidates', 0)}",
      f"- background evidence: {evidence.get('background_evidence', 0)}",
      f"- no paper evidence: {evidence.get('no_paper_evidence', 0)}",
      f"- weak matches: {evidence.get('weak_matches', 0)}",
      f"- high quality sources: {evidence.get('high_quality_sources', 0)}",
      f"- gap type counts: {evidence.get('gap_type_counts', {})}",
      f"- caveat: {evidence.get('caveat', 'Paper links are evidence candidates only.')}",
      "",
      "## 7. Web / Company Signal Highlights",
      "",
    ],
  )
  for row in summary.get("web_signals_by_company", [])[:8]:
    lines.append(
      f"- company: {row.get('normalized_company') or row.get('company')} | "
      f"signals: {row.get('signal_count')} | patents: {row.get('linked_patents')}",
    )
  for row in summary.get("web_signals_by_cluster", [])[:8]:
    lines.append(
      f"- cluster: {row.get('cluster_id')} | signals: {row.get('signal_count')} | types: {row.get('signal_types')}",
    )
  lines.append("- Web/company signals are business context candidates and may not map to specific patents.")

  lines.extend(["", "## 8. SME Action Plan", ""])
  for section in summary.get("sme_action_plan", []):
    lines.append(f"### {section.get('action_category')}")
    for item in section.get("items", [])[:6]:
      lines.append(f"- {item}")
    lines.append("")

  lines.extend(["## 9. Evidence Gaps and Human Review", ""])
  for gap in summary.get("evidence_gaps", [])[:15]:
    lines.append(
      f"- {gap.get('publication_number')} | {gap.get('element_id')} | "
      f"{gap.get('gap_type')} | {gap.get('recommended_action')}",
    )
  human_review = [
    patent.get("publication_number")
    for patent in summary.get("priority_patents", [])
    if patent.get("human_review_required")
  ]
  if human_review:
    lines.append(f"- human review required patents: {', '.join(human_review)}")

  lines.extend(["", "## 10. Next Update Recommendation", ""])
  for rec in summary.get("next_update_recommendations", []):
    lines.append(f"- {rec}")

  lines.extend(["", "## 11. Caveats", ""])
  for caveat in summary.get("caveats", []):
    lines.append(f"- {caveat}")

  return "\n".join(lines)


def save_synthesis_report(markdown: str, output_dir: str | Path) -> str:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  path = out / "carbon_fiber_evidence_map_v1.md"
  path.write_text(markdown, encoding="utf-8")
  return str(path)
