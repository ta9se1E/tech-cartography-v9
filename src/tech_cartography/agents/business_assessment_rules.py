"""Rule-based business assessment scoring."""

from __future__ import annotations

from collections import Counter
from typing import Any

from tech_cartography.evidence.company_name_normalizer import normalize_company_name

BUSINESS_SIGNAL_RELATION = "business_signal_candidate"
BACKGROUND_RELATION = "technology_background_signal"
WEAK_RELATION = "weak_signal"

STRONG_SIGNAL_TYPES = {
  "product_launch",
  "capital_investment",
  "production_expansion",
  "partnership",
  "joint_development",
  "ir_strategy",
  "customer_adoption",
}
MEDIUM_SIGNAL_TYPES = {
  "exhibition",
  "market_report",
  "industry_news",
  "patent_related_news",
}
AUX_SIGNAL_TYPES = {"hiring", "regulation"}

MAJOR_COMPANIES = {
  "TORAY",
  "TEIJIN",
  "MITSUBISHI CHEMICAL",
  "HYOSUNG",
  "SGL CARBON",
  "HEXCEL",
  "SOLVAY",
  "ZOLTEK",
}

SME_OPPORTUNITY_CLUSTERS = {
  "surface_interface",
  "application_pressure_aerospace",
}
CORE_MANUFACTURING_CLUSTER = "core_manufacturing"
DESIGN_AROUND_CLUSTERS = {"surface_interface", "bundle_prepreg", "application_pressure_aerospace"}


def _filter_links(web_links: list[dict[str, Any]]) -> list[dict[str, Any]]:
  return [link for link in web_links if str(link.get("relation")) != "unrelated"]


def score_web_signal_strength(web_links: list[dict[str, Any]]) -> dict[str, Any]:
  links = _filter_links(web_links)
  business = [link for link in links if link.get("relation") == BUSINESS_SIGNAL_RELATION]
  weak = [link for link in links if link.get("relation") == WEAK_RELATION]
  high_quality = sum(1 for link in business if link.get("source_quality_level") in {"high", "medium"})
  low_only = business and all(link.get("source_quality_level") in {"low", "unknown", None} for link in business)

  score = 0.25
  reasons: list[str] = []
  if business:
    score += min(0.4, 0.1 * len(business))
    reasons.append(f"{len(business)} business_signal_candidate link(s)")
  if high_quality:
    score += min(0.2, 0.08 * high_quality)
    reasons.append(f"{high_quality} high/medium quality source(s)")
  if weak and not business:
    score += 0.05
    reasons.append("weak_signal only")
  if low_only:
    score -= 0.1
    reasons.append("business signals have low source quality only")
  if not links:
    score -= 0.1
    reasons.append("no relevant web signal links")

  return {
    "score": round(max(0.0, min(1.0, score)), 3),
    "reasons": reasons,
    "business_signal_count": len(business),
    "web_signal_count": len(links),
  }


def score_company_activity(web_links: list[dict[str, Any]]) -> dict[str, Any]:
  links = _filter_links(web_links)
  type_counter = Counter(str(link.get("signal_type") or "unknown") for link in links)
  score = 0.2
  reasons: list[str] = []
  strong_hits = sum(type_counter.get(t, 0) for t in STRONG_SIGNAL_TYPES)
  medium_hits = sum(type_counter.get(t, 0) for t in MEDIUM_SIGNAL_TYPES)
  if strong_hits:
    score += min(0.45, 0.12 * strong_hits)
    reasons.append(f"strong activity signals: {strong_hits}")
  if medium_hits:
    score += min(0.2, 0.06 * medium_hits)
    reasons.append(f"background activity signals: {medium_hits}")
  if type_counter.get("unknown", 0) and not strong_hits:
    score -= 0.05
    reasons.append("unknown signal types present")
  return {
    "score": round(max(0.0, min(1.0, score)), 3),
    "reasons": reasons,
    "signal_types": dict(type_counter),
  }


def score_technical_business_alignment(
  technical_summary: dict[str, Any] | None,
  web_links: list[dict[str, Any]],
) -> dict[str, Any]:
  technical_summary = technical_summary or {}
  tech_conf = str(technical_summary.get("overall_technical_confidence") or "unknown")
  tech_score = float(technical_summary.get("overall_technical_score") or 0.0)
  business_links = [link for link in web_links if link.get("relation") == BUSINESS_SIGNAL_RELATION]

  score = 0.25
  reasons: list[str] = []
  human_review_required = False

  if tech_conf in {"high", "medium"} and business_links:
    score += 0.35
    reasons.append("technical confidence and business_signal_candidate align")
  elif tech_conf in {"low", "unknown"} and business_links:
    score += 0.1
    human_review_required = True
    reasons.append("business signals present but technical evidence is weak")
  elif tech_conf in {"high", "medium"} and not business_links:
    score += 0.15
    reasons.append("technical attention; business signals not confirmed")
  else:
    reasons.append("limited technical and business alignment")

  score += min(0.15, tech_score * 0.15)
  return {
    "score": round(max(0.0, min(1.0, score)), 3),
    "reasons": reasons,
    "human_review_required": human_review_required,
    "technical_confidence": tech_conf,
    "technical_score": tech_score,
  }


def score_ip_watch_priority(
  patent: dict[str, Any] | None,
  technical_summary: dict[str, Any] | None,
  web_links: list[dict[str, Any]],
) -> dict[str, Any]:
  patent = patent or {}
  technical_summary = technical_summary or {}
  score = 0.2
  reasons: list[str] = []

  if patent.get("recommended_action") in {"fulltext_fetch", "priority_review"}:
    score += 0.15
    reasons.append("high-ranked patent candidate")
  if float(patent.get("total_score") or 0) >= 0.7:
    score += 0.1
    reasons.append("high patent ranking score")
  if float(technical_summary.get("overall_technical_score") or 0) >= 0.6:
    score += 0.15
    reasons.append("strong technical screening score")
  business_links = [link for link in web_links if link.get("relation") == BUSINESS_SIGNAL_RELATION]
  if business_links:
    score += min(0.2, 0.08 * len(business_links))
    reasons.append("business web signals linked")
  assignee = normalize_company_name(patent.get("assignee"))
  if assignee in MAJOR_COMPANIES:
    score += 0.15
    reasons.append(f"major assignee: {assignee}")

  return {
    "score": round(max(0.0, min(1.0, score)), 3),
    "reasons": reasons,
    "watch_priority": "high" if score >= 0.65 else "medium" if score >= 0.4 else "low",
  }


def score_sme_entry_opportunity(
  patent: dict[str, Any] | None,
  technical_summary: dict[str, Any] | None,
  web_links: list[dict[str, Any]],
) -> dict[str, Any]:
  patent = patent or {}
  cluster = str(patent.get("primary_cluster_id") or "")
  score = 0.2
  reasons: list[str] = []
  opportunity_type = "monitor_only"

  if cluster == CORE_MANUFACTURING_CLUSTER:
    score += 0.15
    opportunity_type = "watch_avoid_or_partner"
    reasons.append("core manufacturing area: caution, partnership, or design-around candidate")
  elif cluster in SME_OPPORTUNITY_CLUSTERS:
    score += 0.35
    opportunity_type = "sme_entry_candidate"
    reasons.append("surface/interface or application-adjacent cluster may offer SME entry candidate")
  elif "surface" in str(patent.get("title", "")).lower() or "interface" in str(patent.get("title", "")).lower():
    score += 0.25
    opportunity_type = "sme_entry_candidate"
    reasons.append("surface/interface theme may offer SME entry candidate")

  business_links = [link for link in web_links if link.get("relation") == BUSINESS_SIGNAL_RELATION]
  if len(business_links) >= 2:
    score -= 0.05
    reasons.append("strong company signals may indicate competitive intensity")

  gaps = technical_summary.get("key_evidence_gaps", []) if technical_summary else []
  if gaps:
    score += 0.1
    opportunity_type = "verification_candidate"
    reasons.append("evidence gaps suggest verification room, not proven entry opportunity")

  return {
    "score": round(max(0.0, min(1.0, score)), 3),
    "reasons": reasons,
    "opportunity_type": opportunity_type,
  }


def score_design_around_opportunity(
  technical_summary: dict[str, Any] | None,
  evidence_gaps: list[dict[str, Any]] | None = None,
  patent: dict[str, Any] | None = None,
) -> dict[str, Any]:
  technical_summary = technical_summary or {}
  patent = patent or {}
  score = 0.15
  reasons: list[str] = []

  weak_points = list(technical_summary.get("weak_or_uncertain_points", []))
  if weak_points:
    score += min(0.25, 0.08 * len(weak_points))
    reasons.append("weak or uncertain technical points present")
  if evidence_gaps:
    score += min(0.2, 0.06 * len(evidence_gaps))
    reasons.append("evidence gaps may leave room for design-around candidate")
  if str(patent.get("primary_cluster_id")) in DESIGN_AROUND_CLUSTERS:
    score += 0.15
    reasons.append("adjacent cluster may support differentiation candidate")
  if technical_summary.get("recommended_reader_action") == "expert_review_required":
    score += 0.1
    reasons.append("expert review recommended for claim scope")

  return {
    "score": round(max(0.0, min(1.0, score)), 3),
    "reasons": reasons,
  }


def score_overall_business_confidence(scores: dict[str, Any]) -> dict[str, Any]:
  positive = (
    scores.get("web_signal_strength", {}).get("score", 0.0) * 0.25
    + scores.get("company_activity", {}).get("score", 0.0) * 0.2
    + scores.get("technical_business_alignment", {}).get("score", 0.0) * 0.2
    + scores.get("ip_watch_priority", {}).get("score", 0.0) * 0.2
    + scores.get("sme_entry_opportunity", {}).get("score", 0.0) * 0.05
    + scores.get("design_around_opportunity", {}).get("score", 0.0) * 0.1
  )
  overall = max(0.0, min(1.0, positive + 0.1))

  if scores.get("technical_business_alignment", {}).get("human_review_required"):
    overall = min(overall, 0.55)

  if overall >= 0.7:
    confidence = "high"
  elif overall >= 0.45:
    confidence = "medium"
  elif overall >= 0.2:
    confidence = "low"
  else:
    confidence = "unknown"

  return {
    "overall_score": round(overall, 3),
    "overall_confidence": confidence,
    "human_review_required": scores.get("technical_business_alignment", {}).get("human_review_required", False)
    or overall < 0.3,
  }


def classify_business_action(scores: dict[str, Any]) -> str:
  overall = scores.get("overall", {})
  confidence = overall.get("overall_confidence", "unknown")
  ip_watch = scores.get("ip_watch_priority", {}).get("watch_priority", "low")
  sme_type = scores.get("sme_entry_opportunity", {}).get("opportunity_type", "monitor_only")
  design_score = scores.get("design_around_opportunity", {}).get("score", 0.0)
  alignment = scores.get("technical_business_alignment", {})

  if overall.get("human_review_required"):
    return "expert_ip_review_required"
  if confidence == "high" or ip_watch == "high":
    return "monitor_company_signals"
  if sme_type == "sme_entry_candidate":
    return "explore_partnership_or_customer_need"
  if design_score >= 0.45:
    return "investigate_design_around"
  if alignment.get("technical_confidence") in {"high", "medium"} and not scores.get("web_signal_strength", {}).get("business_signal_count"):
    return "check_technical_evidence_before_action"
  if confidence == "low":
    return "monitor_only"
  return "read_patent_and_examples_first"
