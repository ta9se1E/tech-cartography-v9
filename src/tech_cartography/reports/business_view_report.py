"""Business view assessment report."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any


def build_business_view_summary(result: dict[str, Any]) -> dict[str, Any]:
  assessments = list(result.get("business_assessments", []))
  company_counter: Counter[str] = Counter()
  cluster_counter: Counter[str] = Counter()
  for assessment in assessments:
    if assessment.get("assignee"):
      company_counter[str(assessment.get("assignee"))] += 1
    if assessment.get("primary_cluster_id"):
      cluster_counter[str(assessment.get("primary_cluster_id"))] += 1

  return {
    "assessed_patents": result.get("total_patents", 0),
    "high_business_priority": result.get("high_business_priority_patents", 0),
    "medium_business_priority": result.get("medium_business_priority_patents", 0),
    "low_business_priority": result.get("low_business_priority_patents", 0),
    "monitor_only": result.get("monitor_only_patents", 0),
    "expert_review_required": result.get("expert_review_required", 0),
    "sme_opportunity_candidates": result.get("sme_opportunity_candidates", []),
    "design_around_candidates": result.get("design_around_candidates", []),
    "common_business_signals": result.get("common_business_signals", {}),
    "common_business_risks": result.get("common_business_risks", {}),
    "business_assessments": assessments,
    "assessment_items": result.get("assessment_items", []),
    "competitive_watch_companies": dict(company_counter.most_common(10)),
    "competitive_watch_clusters": dict(cluster_counter.most_common(10)),
    "next_phases": ["Synthesis Report", "Monthly / Biweekly Evidence Map Update"],
  }


def render_business_view_markdown(summary: dict[str, Any]) -> str:
  lines = [
    "# Business View Assessment Report",
    "",
    "## 1. Summary",
    "",
    f"- assessed patents: {summary.get('assessed_patents', 0)}",
    f"- high business priority: {summary.get('high_business_priority', 0)}",
    f"- medium business priority: {summary.get('medium_business_priority', 0)}",
    f"- low business priority: {summary.get('low_business_priority', 0)}",
    f"- monitor only: {summary.get('monitor_only', 0)}",
    f"- expert review required: {summary.get('expert_review_required', 0)}",
    f"- SME opportunity candidates: {len(summary.get('sme_opportunity_candidates', []))}",
    f"- design-around candidates: {len(summary.get('design_around_candidates', []))}",
    f"- common business signals: {summary.get('common_business_signals', {})}",
    f"- common business risks: {summary.get('common_business_risks', {})}",
    "",
    "## 2. Patent Business Assessments",
    "",
  ]

  for assessment in summary.get("business_assessments", []):
    lines.extend(
      [
        f"### {assessment.get('publication_number')}",
        f"- title: {assessment.get('patent_title')}",
        f"- assignee: {assessment.get('assignee')}",
        f"- primary cluster: {assessment.get('primary_cluster_name') or assessment.get('primary_cluster_id')}",
        f"- overall business confidence: {assessment.get('overall_business_confidence')}",
        f"- overall business score: {assessment.get('overall_business_score')}",
        f"- business summary: {assessment.get('business_summary')}",
        f"- commercialization signals: {', '.join(assessment.get('commercialization_signals', [])[:2])}",
        f"- competitive watch points: {', '.join(assessment.get('competitive_watch_points', [])[:2])}",
        f"- SME opportunity points: {', '.join(assessment.get('sme_opportunity_points', [])[:2])}",
        f"- design-around hints: {', '.join(assessment.get('design_around_or_differentiation_hints', [])[:2])}",
        f"- partnership / customer hints: {', '.join(assessment.get('partnership_or_customer_hints', [])[:2])}",
        f"- business risks: {', '.join(assessment.get('business_risks', [])[:2])}",
        f"- recommended next actions: {', '.join(assessment.get('recommended_next_actions', [])[:3])}",
        f"- recommended reader action: {assessment.get('recommended_reader_action')}",
        "",
      ],
    )

  lines.extend(["## 3. Business Assessment Items", ""])
  for item in summary.get("assessment_items", [])[:25]:
    lines.append(
      f"- {item.get('publication_number')} | {item.get('business_topic')} | "
      f"{item.get('assessment_type')} | {item.get('business_confidence')} | "
      f"{str(item.get('assessment', ''))[:60]}",
    )

  lines.extend(["", "## 4. SME Opportunity View", ""])
  for row in summary.get("sme_opportunity_candidates", []):
    lines.append(f"- {row.get('publication_number')}: {row.get('points')}")
  lines.append("- 参入余地候補 / 検証余地候補 / 協業候補として扱い、参入可能とは断定しない")

  lines.extend(["", "## 5. Competitive Watch View", ""])
  lines.append(f"- companies with stronger watch signals: {summary.get('competitive_watch_companies', {})}")
  lines.append(f"- clusters with business signals: {summary.get('competitive_watch_clusters', {})}")
  lines.append("- 手入力Web signalに依存するため、継続的な更新とURL確認が必要")

  lines.extend(
    [
      "",
      "## 6. Caveats",
      "",
      "- 本評価は特許・論文Evidence Candidate・Web/企業シグナルを統合した一次評価である",
      "- Web signalは事業化の兆候候補であり、特定特許の実施や商用化を証明するものではない",
      "- 企業単位のニュースは個別特許と直接対応しない場合がある",
      "- SourceQualityは情報源としての扱いやすさであり、内容の正しさや事業成功を保証しない",
      "- 特許の有効性・侵害・FTO判断ではない",
      "- 中小企業の実行判断には、顧客ヒアリング、実験検証、専門家レビューが必要",
      "",
      "## 7. Next Phase",
      "",
    ],
  )
  for step in summary.get("next_phases", []):
    lines.append(f"- {step}")
  return "\n".join(lines)


def save_business_view_report(markdown: str, output_dir: str | Path) -> str:
  path = Path(output_dir) / "business_view_report.md"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(markdown, encoding="utf-8")
  return str(path)
