"""Rule-based synthesis scoring and grouping."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

CONFIDENCE_WEIGHTS = {"high": 0.9, "medium": 0.6, "low": 0.3, "unknown": 0.1}


def _confidence_value(label: str | None) -> float:
  return CONFIDENCE_WEIGHTS.get(str(label or "unknown"), 0.1)


def assign_synthesis_importance(item: dict[str, Any]) -> str:
  score = float(item.get("priority_score", item.get("score", 0.0)) or 0.0)
  if item.get("human_review_required") or score >= 0.72:
    return "high"
  if score >= 0.45:
    return "medium"
  return "low"


def assign_synthesis_confidence(item: dict[str, Any]) -> str:
  tech = _confidence_value(item.get("technical_confidence") or item.get("overall_technical_confidence"))
  biz = _confidence_value(item.get("business_confidence") or item.get("overall_business_confidence"))
  evidence = float(item.get("evidence_support_score", 0.0) or 0.0)
  combined = tech * 0.4 + biz * 0.35 + evidence * 0.25
  if combined >= 0.7:
    return "high"
  if combined >= 0.45:
    return "medium"
  if combined >= 0.2:
    return "low"
  return "unknown"


def build_global_caveats() -> list[str]:
  return [
    "本レポートは研究開発・知財・事業開発の一次判断材料である",
    "特許の有効性、侵害、FTO、法的判断を保証しない",
    "論文Evidence Candidateは特許主張の直接証明ではない",
    "Web/Company Signalは事業化や実施の証明ではない",
    "SourceQualityは参照元としての扱いやすさであり、内容の正しさを保証しない",
    "Claim Element抽出、分類、ランキングはルールベースを含み、人間確認が必要",
    "最終判断には専門家レビュー、実験検証、顧客ヒアリングが必要",
  ]


def select_priority_patents(
  top20: list[dict[str, Any]],
  technical_summary: list[dict[str, Any]],
  business_summary: list[dict[str, Any]],
  top5_candidates: list[dict[str, Any]] | None = None,
  business_assessments: list[dict[str, Any]] | None = None,
  evidence_gaps: list[dict[str, Any]] | None = None,
  top_n: int = 10,
) -> list[dict[str, Any]]:
  tech_by_pub = {str(row.get("publication_number")): row for row in technical_summary}
  biz_by_pub = {str(row.get("publication_number")): row for row in business_summary}
  biz_assess_by_pub = {str(row.get("publication_number")): row for row in (business_assessments or [])}
  top5_pubs = {str(row.get("publication_number")) for row in (top5_candidates or [])}
  gap_counts = Counter(str(gap.get("publication_number")) for gap in (evidence_gaps or []))

  scored: list[dict[str, Any]] = []
  for patent in top20:
    pub = str(patent.get("publication_number", ""))
    if not pub:
      continue
    tech = tech_by_pub.get(pub, {})
    biz = biz_by_pub.get(pub, {})
    biz_assess = biz_assess_by_pub.get(pub, {})
    reasons: list[str] = []
    score = 0.0

    rank = int(float(patent.get("rank", 99) or 99))
    score += max(0.0, (21 - rank) * 0.02)
    if rank <= 5:
      reasons.append(f"top rank {rank}")

    tech_conf = str(tech.get("overall_technical_confidence", "unknown"))
    if tech_conf == "high":
      score += 0.22
      reasons.append("technical confidence high")
    elif tech_conf == "medium":
      score += 0.12
      reasons.append("technical confidence medium")

    biz_conf = str(biz.get("overall_business_confidence", "unknown"))
    if biz_conf == "high":
      score += 0.18
      reasons.append("business confidence high")
    elif biz_conf == "medium":
      score += 0.1
      reasons.append("business confidence medium")

    if tech.get("strongest_supported_points"):
      score += 0.08
      reasons.append("supporting evidence candidate points present")

    if biz_assess.get("commercialization_signals") or biz_assess.get("partnership_or_customer_hints"):
      score += 0.1
      reasons.append("business signal candidate linked")

    if pub in top5_pubs or patent.get("recommended_action") in {"fulltext_fetch", "priority_review"}:
      score += 0.12
      reasons.append("top5 fulltext candidate or priority review")

    noise_score = float(patent.get("noise_score", 0.0) or 0.0)
    if noise_score >= 0.5:
      score -= 0.15
      reasons.append("noise candidate lowered")

    gap_count = gap_counts.get(pub, 0)
    human_review_required = gap_count >= 3 or any(
      item.get("assessment_type") == "human_review_required"
      for item in biz_assess.get("assessment_items", [])
    )
    if human_review_required:
      reasons.append("human review recommended due to evidence gaps or misalignment")

    item = {
      "publication_number": pub,
      "title": patent.get("title") or patent.get("patent_title") or tech.get("patent_title"),
      "assignee": patent.get("assignee") or tech.get("assignee"),
      "primary_cluster_id": patent.get("primary_cluster_id"),
      "primary_cluster_name": patent.get("primary_cluster_name"),
      "rank": rank,
      "technical_confidence": tech_conf,
      "business_confidence": biz_conf,
      "priority_score": round(max(0.0, min(1.0, score)), 3),
      "why_read": "; ".join(reasons[:4]) or "ranked top patent candidate",
      "next_check": tech.get("recommended_reader_action") or biz.get("recommended_reader_action") or "read_patent_and_examples_first",
      "human_review_required": human_review_required,
      "evidence_gap_count": gap_count,
    }
    item["importance"] = assign_synthesis_importance(item)
    item["confidence"] = assign_synthesis_confidence(
      {
        "overall_technical_confidence": tech_conf,
        "overall_business_confidence": biz_conf,
        "evidence_support_score": 0.7 if tech.get("strongest_supported_points") else 0.2,
      },
    )
    scored.append(item)

  scored.sort(key=lambda row: (row["priority_score"], -row.get("rank", 99)), reverse=True)
  return scored[:top_n]


def synthesize_cluster_signals(
  cluster_summary: list[dict[str, Any]],
  technical_summary: list[dict[str, Any]],
  business_summary: list[dict[str, Any]],
  web_signals_by_cluster: list[dict[str, Any]] | None = None,
  evidence_gaps: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
  tech_by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for row in technical_summary:
    cluster_id = str(row.get("primary_cluster_id") or "")
    if cluster_id:
      tech_by_cluster[cluster_id].append(row)

  biz_by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for row in business_summary:
    cluster_id = str(row.get("primary_cluster_id") or "")
    if cluster_id:
      biz_by_cluster[cluster_id].append(row)

  web_by_cluster = {
    str(row.get("cluster_id") or row.get("primary_cluster_id")): row
    for row in (web_signals_by_cluster or [])
  }
  gap_by_cluster = Counter(
    str(gap.get("primary_cluster_id") or "")
    for gap in (evidence_gaps or [])
    if gap.get("primary_cluster_id")
  )

  results: list[dict[str, Any]] = []
  for cluster in cluster_summary:
    cluster_id = str(cluster.get("cluster_id", ""))
    tech_rows = tech_by_cluster.get(cluster_id, [])
    biz_rows = biz_by_cluster.get(cluster_id, [])
    high_tech = sum(1 for row in tech_rows if row.get("overall_technical_confidence") in {"high", "medium"})
    high_biz = sum(1 for row in biz_rows if row.get("overall_business_confidence") in {"high", "medium"})
    web_row = web_by_cluster.get(cluster_id, {})
    gap_count = gap_by_cluster.get(cluster_id, 0)

    categories: list[str] = []
    if cluster.get("patent_count", 0) >= 3:
      categories.append("注目クラスタ")
    if high_tech:
      categories.append("裏取り候補ありクラスタ")
    if web_row.get("signal_count") or high_biz:
      categories.append("事業シグナル候補ありクラスタ")
    if gap_count >= 2:
      categories.append("追加確認が必要なクラスタ")
    if not categories:
      categories.append("監視クラスタ")

    results.append(
      {
        "cluster_id": cluster_id,
        "name": cluster.get("name"),
        "description": cluster.get("description"),
        "patent_count": cluster.get("patent_count", 0),
        "representative_patents": cluster.get("representative_patents", [])[:5],
        "top_assignees": cluster.get("top_assignees", [])[:5],
        "categories": categories,
        "technical_signal": f"{high_tech} patent(s) with medium/high technical confidence",
        "business_signal": web_row.get("signal_types") or (
          f"{high_biz} patent(s) with medium/high business confidence" if high_biz else "limited business signal"
        ),
        "evidence_gaps": gap_count,
        "next_action": "read representative patents and verify claim/paper alignment"
        if "裏取り候補ありクラスタ" in categories
        else "monitor cluster and update web signals",
      },
    )
  return results


def synthesize_evidence_strength(
  claim_paper_summary: dict[str, Any] | None,
  source_quality_results: list[dict[str, Any]] | None,
  evidence_gaps: list[dict[str, Any]] | None,
) -> dict[str, Any]:
  summary = claim_paper_summary or {}
  quality_counter = Counter(str(row.get("source_quality_level")) for row in (source_quality_results or []))
  gap_counter = Counter(str(gap.get("gap_type")) for gap in (evidence_gaps or []))
  return {
    "supporting_evidence_candidates": summary.get("supporting_evidence_candidates", 0),
    "background_evidence": summary.get("background_evidence", 0),
    "weak_matches": summary.get("weak_matches", 0),
    "no_paper_evidence": summary.get("no_paper_evidence", 0),
    "high_quality_sources": summary.get("high_quality_sources", quality_counter.get("high", 0)),
    "relation_counts": summary.get("relation_counts", {}),
    "quality_counts": dict(quality_counter) or summary.get("quality_counts", {}),
    "gap_type_counts": dict(gap_counter),
    "total_evidence_gaps": len(evidence_gaps or []),
    "caveat": "Paper links are evidence candidates, not direct proof of patent claims.",
  }


def synthesize_sme_action_plan(
  priority_patents: list[dict[str, Any]],
  business_summary: list[dict[str, Any]],
  technical_summary: list[dict[str, Any]],
  business_assessments: list[dict[str, Any]] | None = None,
  web_signals_by_company: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
  biz_by_pub = {str(row.get("publication_number")): row for row in business_summary}
  tech_by_pub = {str(row.get("publication_number")): row for row in technical_summary}
  assess_by_pub = {str(row.get("publication_number")): row for row in (business_assessments or [])}

  plan: list[dict[str, Any]] = []

  read_now = [
    {
      "publication_number": row["publication_number"],
      "title": row.get("title"),
      "reason": row.get("why_read"),
      "next_check": row.get("next_check"),
    }
    for row in priority_patents[:5]
  ]
  if read_now:
    plan.append({"action_category": "今すぐ読むべき特許", "items": read_now})

  examples_check = [
    {
      "publication_number": pub,
      "title": tech.get("patent_title"),
      "reason": "measurement or implementation risks flagged",
    }
    for pub, tech in tech_by_pub.items()
    if tech.get("measurement_or_validation_risks") or tech.get("implementation_risks")
  ][:5]
  if examples_check:
    plan.append({"action_category": "実施例・測定条件を確認すべき特許", "items": examples_check})

  paper_verify = [
    {
      "publication_number": pub,
      "points": tech.get("strongest_supported_points", [])[:2],
      "gaps": tech.get("key_evidence_gaps", [])[:2],
    }
    for pub, tech in tech_by_pub.items()
    if tech.get("strongest_supported_points") or tech.get("key_evidence_gaps")
  ][:6]
  if paper_verify:
    plan.append({"action_category": "論文で裏取りすべき技術要素", "items": paper_verify})

  monitor_companies = [
    {
      "company": row.get("normalized_company") or row.get("company"),
      "signal_count": row.get("signal_count"),
      "linked_patents": row.get("linked_patents"),
    }
    for row in (web_signals_by_company or [])[:5]
  ]
  if monitor_companies:
    plan.append({"action_category": "企業動向を監視すべき会社", "items": monitor_companies})

  entry_candidates = [
    {
      "publication_number": pub,
      "points": assess.get("sme_opportunity_points", [])[:2],
    }
    for pub, assess in assess_by_pub.items()
    if assess.get("sme_opportunity_points")
  ]
  if entry_candidates:
    plan.append({"action_category": "参入余地候補", "items": entry_candidates})

  design_around = [
    {
      "publication_number": pub,
      "hints": assess.get("design_around_or_differentiation_hints", [])[:2],
    }
    for pub, assess in assess_by_pub.items()
    if assess.get("design_around_or_differentiation_hints")
  ]
  if design_around:
    plan.append({"action_category": "回避設計・差別化候補", "items": design_around})

  expert_review = [
    {
      "publication_number": row["publication_number"],
      "reason": "human review or expert reader action recommended",
    }
    for row in priority_patents
    if row.get("human_review_required")
    or biz_by_pub.get(row["publication_number"], {}).get("recommended_reader_action") == "expert_ip_review_required"
  ]
  if expert_review:
    plan.append({"action_category": "専門家レビュー対象", "items": expert_review})

  monitor_only = [
    {
      "publication_number": pub,
      "reason": biz.get("recommended_reader_action") or "monitor_only",
    }
    for pub, biz in biz_by_pub.items()
    if biz.get("recommended_reader_action") == "monitor_only"
  ][:5]
  if monitor_only:
    plan.append({"action_category": "監視のみ", "items": monitor_only})

  return plan


def synthesize_monitoring_recommendations(
  cluster_summary: list[dict[str, Any]],
  evidence_gaps: list[dict[str, Any]] | None,
  web_signals_by_cluster: list[dict[str, Any]] | None = None,
  retrieval_summary: dict[str, Any] | None = None,
) -> list[str]:
  recommendations: list[str] = []
  top_clusters = sorted(cluster_summary, key=lambda c: c.get("patent_count", 0), reverse=True)[:3]
  for cluster in top_clusters:
    terms = cluster.get("representative_terms", [])[:3]
    if terms:
      recommendations.append(f"次回検索で増やすべき語候補: {', '.join(terms)} ({cluster.get('name')})")

  gap_types = Counter(str(gap.get("gap_type")) for gap in (evidence_gaps or []))
  if gap_types.get("claim_only_no_description_support"):
    recommendations.append("除外・注意すべきノイズ語候補: broad resin/general composite terms without carbon fiber context")

  assignees = {
    assignee
    for cluster in cluster_summary
    for assignee in cluster.get("top_assignees", [])[:2]
    if assignee and assignee != "Unknown"
  }
  if assignees:
    recommendations.append(f"追加すべき企業監視候補: {', '.join(sorted(assignees)[:5])}")

  if not web_signals_by_cluster:
    recommendations.append("追加すべきWeb signal: production_expansion, partnership, customer_adoption for top assignees")
  else:
    weak_clusters = [
      row.get("cluster_id")
      for row in web_signals_by_cluster
      if int(row.get("signal_count", 0) or 0) == 0
    ][:3]
    if weak_clusters:
      recommendations.append(f"Web signal追加候補クラスタ: {', '.join(weak_clusters)}")

  if retrieval_summary:
    recommendations.append("月次/隔週更新に向けた候補: rerun BigQuery light retrieval and refresh web signal CSV")

  recommendations.append("次回はevidence_gapsとbusiness_assessmentsの差分を確認し、優先特許リストを更新する")
  return recommendations
