"""Technical view assessment report."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def build_technical_view_summary(result: dict[str, Any]) -> dict[str, Any]:
  assessments = list(result.get("technical_assessments", []))
  items = list(result.get("assessment_items", []))
  type_counter = Counter(
    item.get("element_type") or item.get("technical_topic")
    for item in items
    if item.get("element_type")
  )
  gap_counter = Counter(result.get("common_evidence_gaps", {}).keys())
  return {
    "assessed_patents": result.get("total_patents", 0),
    "high_confidence": result.get("high_confidence_patents", 0),
    "medium_confidence": result.get("medium_confidence_patents", 0),
    "low_confidence": result.get("low_confidence_patents", 0),
    "human_review_required": result.get("human_review_required", 0),
    "common_technical_risks": result.get("common_technical_risks", {}),
    "common_evidence_gaps": result.get("common_evidence_gaps", {}),
    "technical_assessments": assessments,
    "assessment_items": items,
    "cross_patent_insights": _build_cross_patent_insights(assessments, items),
    "warnings": result.get("warnings", []),
    "errors": result.get("errors", []),
    "next_phases": [
      "Business View Agent",
      "Web / Company Signal Mapping",
      "Synthesis Report",
    ],
  }


def _build_cross_patent_insights(
  assessments: list[dict[str, Any]],
  items: list[dict[str, Any]],
) -> dict[str, Any]:
  topic_support: dict[str, int] = defaultdict(int)
  topic_gaps: dict[str, int] = defaultdict(int)
  keywords = {
    "surface treatment": ["surface", "interface", "adhesion"],
    "carbonization": ["carbonization", "炭化"],
    "prepreg": ["prepreg", "impregnation"],
    "pressure vessel": ["pressure vessel", "tank", "圧力容器"],
  }
  for assessment in assessments:
    for point in assessment.get("strongest_supported_points", []):
      lowered = point.lower()
      for topic, terms in keywords.items():
        if any(term in lowered for term in terms):
          topic_support[topic] += 1
    for gap in assessment.get("key_evidence_gaps", []):
      lowered = gap.lower()
      for topic, terms in keywords.items():
        if any(term in lowered for term in terms):
          topic_gaps[topic] += 1
  return {
    "topics_with_more_support_candidates": dict(topic_support),
    "topics_with_more_gaps": dict(topic_gaps),
    "note": "Cross-patent comparison is provisional and based on rule-based screening only.",
  }


def render_technical_view_markdown(summary: dict[str, Any]) -> str:
  lines = [
    "# Technical View Assessment Report",
    "",
    "## 1. Summary",
    "",
    f"- assessed patents: {summary.get('assessed_patents', 0)}",
    f"- high confidence: {summary.get('high_confidence', 0)}",
    f"- medium confidence: {summary.get('medium_confidence', 0)}",
    f"- low confidence: {summary.get('low_confidence', 0)}",
    f"- human review required: {summary.get('human_review_required', 0)}",
    f"- common technical risks: {summary.get('common_technical_risks', {})}",
    f"- common evidence gaps: {summary.get('common_evidence_gaps', {})}",
    "",
    "## 2. Patent Technical Assessments",
    "",
  ]

  for assessment in summary.get("technical_assessments", []):
    lines.extend(
      [
        f"### {assessment.get('publication_number')}",
        f"- title: {assessment.get('patent_title')}",
        f"- assignee: {assessment.get('assignee')}",
        f"- overall technical confidence: {assessment.get('overall_technical_confidence')}",
        f"- overall technical score: {assessment.get('overall_technical_score')}",
        f"- technical summary: {assessment.get('technical_summary')}",
        f"- strongest supported points: {', '.join(assessment.get('strongest_supported_points', [])[:3])}",
        f"- weak or uncertain points: {', '.join(assessment.get('weak_or_uncertain_points', [])[:3])}",
        f"- implementation risks: {', '.join(assessment.get('implementation_risks', [])[:2])}",
        f"- measurement / validation risks: {', '.join(assessment.get('measurement_or_validation_risks', [])[:2])}",
        f"- recommended next checks: {', '.join(assessment.get('recommended_next_checks', [])[:3])}",
        f"- recommended reader action: {assessment.get('recommended_reader_action')}",
        "",
      ],
    )

  lines.extend(["## 3. Technical Assessment Items", ""])
  lines.append(
    "| patent | topic | type | assessment | confidence | evidence basis | uncertainty | recommended check |",
  )
  lines.append("|---|---|---|---|---|---|---|---|")
  for item in summary.get("assessment_items", [])[:25]:
    basis = "; ".join(item.get("evidence_basis", [])[:2]).replace("|", "/")
    lines.append(
      f"| {item.get('publication_number')} | {str(item.get('technical_topic', ''))[:30]} | "
      f"{item.get('assessment_type')} | {str(item.get('assessment', ''))[:50].replace('|', '/')} | "
      f"{item.get('technical_confidence')} | {basis} | "
      f"{str(item.get('uncertainty', ''))[:40].replace('|', '/')} | "
      f"{str(item.get('recommended_check', ''))[:40].replace('|', '/')} |",
    )

  insights = summary.get("cross_patent_insights", {})
  lines.extend(["", "## 4. Cross-Patent Technical Insights", ""])
  lines.append(f"- topics with more support candidates: {insights.get('topics_with_more_support_candidates', {})}")
  lines.append(f"- topics with more gaps: {insights.get('topics_with_more_gaps', {})}")
  lines.append(f"- note: {insights.get('note', '')}")

  lines.extend(
    [
      "",
      "## 5. Caveats",
      "",
      "- 本評価は特許全文・請求項要素・OpenAlex論文候補に基づく技術的な一次評価である",
      "- 論文候補は特許主張の直接証明ではない",
      "- SourceQualityは参照元の扱いやすさを示すもので、内容の正しさを保証しない",
      "- ClaimElement抽出はルールベースであり、人間確認が必要",
      "- 実装可能性や量産性の判断には、実施例・測定条件・自社工程条件との比較が必要",
      "",
      "## 6. Next Phase",
      "",
    ],
  )
  for step in summary.get("next_phases", []):
    lines.append(f"- {step}")
  return "\n".join(lines)


def save_technical_view_report(markdown: str, output_dir: str | Path) -> str:
  path = Path(output_dir) / "technical_view_report.md"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(markdown, encoding="utf-8")
  return str(path)
