"""Business View Agent for patent business assessment."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from tech_cartography.agents.business_assessment_rules import (
  MEDIUM_SIGNAL_TYPES,
  STRONG_SIGNAL_TYPES,
  classify_business_action,
  score_company_activity,
  score_design_around_opportunity,
  score_ip_watch_priority,
  score_overall_business_confidence,
  score_sme_entry_opportunity,
  score_technical_business_alignment,
  score_web_signal_strength,
)
from tech_cartography.domain.business_assessment import (
  BusinessAssessmentItem,
  PatentBusinessAssessment,
)

FORBIDDEN_ASSERTIONS = (
  "事業化を証明",
  "参入できる",
  "商用化済み",
  "proven commercialization",
  "can enter the market",
  "commercialized",
)


def _sanitize_wording(text: str) -> str:
  sanitized = text
  replacements = {
    "事業化を証明": "事業化シグナル候補がある",
    "参入できる": "参入余地候補がある",
    "商用化済み": "商用化候補の兆候がある",
    "proven commercialization": "commercialization signal candidates exist",
    "can enter the market": "may offer SME entry candidate",
    "commercialized": "commercialization candidate signals exist",
  }
  for old, new in replacements.items():
    sanitized = sanitized.replace(old, new)
  return sanitized


def _confidence_label(score: float) -> str:
  if score >= 0.7:
    return "high"
  if score >= 0.45:
    return "medium"
  if score >= 0.2:
    return "low"
  return "unknown"


def generate_business_assessment_items(
  patent: dict[str, Any] | None,
  technical_summary: dict[str, Any] | None,
  related_web_links: list[dict[str, Any]],
) -> list[dict[str, Any]]:
  patent = patent or {}
  technical_summary = technical_summary or {}
  publication_number = str(patent.get("publication_number") or technical_summary.get("publication_number") or "")
  patent_title = patent.get("title") or patent.get("patent_title") or technical_summary.get("patent_title")
  assignee = patent.get("assignee") or technical_summary.get("assignee")
  cluster_id = patent.get("primary_cluster_id")
  cluster_name = patent.get("primary_cluster_name")

  scores = {
    "web_signal_strength": score_web_signal_strength(related_web_links),
    "company_activity": score_company_activity(related_web_links),
    "technical_business_alignment": score_technical_business_alignment(technical_summary, related_web_links),
    "ip_watch_priority": score_ip_watch_priority(patent, technical_summary, related_web_links),
    "sme_entry_opportunity": score_sme_entry_opportunity(patent, technical_summary, related_web_links),
    "design_around_opportunity": score_design_around_opportunity(technical_summary, None, patent),
  }
  scores["overall"] = score_overall_business_confidence(scores)

  items: list[dict[str, Any]] = []
  tech_conf = technical_summary.get("overall_technical_confidence")
  tech_score = technical_summary.get("overall_technical_score")

  if scores["web_signal_strength"]["business_signal_count"] > 0:
    items.append(
      BusinessAssessmentItem(
        publication_number=publication_number,
        patent_title=patent_title,
        assignee=assignee,
        primary_cluster_id=cluster_id,
        primary_cluster_name=cluster_name,
        business_topic="commercialization signals",
        assessment_type="commercialization_signal",
        assessment=_sanitize_wording(
          "Web/company signal candidates suggest possible commercialization or scale-up activity in this technology area.",
        ),
        business_confidence=_confidence_label(scores["web_signal_strength"]["score"]),
        business_score=scores["web_signal_strength"]["score"],
        evidence_basis=scores["web_signal_strength"]["reasons"],
        web_signal_count=scores["web_signal_strength"]["web_signal_count"],
        business_signal_count=scores["web_signal_strength"]["business_signal_count"],
        technical_confidence=tech_conf,
        technical_score=float(tech_score) if tech_score not in (None, "") else None,
        uncertainty="Company-level web signals may not map to this specific patent.",
        recommended_action="Verify whether the web signal topic matches claim scope and examples.",
        recommended_reader_action="monitor_company_signals",
        caveat="Web signals are business context candidates, not proof of commercialization.",
      ).to_dict(),
    )

  if scores["ip_watch_priority"]["score"] >= 0.4:
    items.append(
      BusinessAssessmentItem(
        publication_number=publication_number,
        patent_title=patent_title,
        assignee=assignee,
        primary_cluster_id=cluster_id,
        primary_cluster_name=cluster_name,
        business_topic="IP watch priority",
        assessment_type="ip_watch_priority",
        assessment="Patent ranking, technical screening, and web signals suggest elevated competitive watch priority.",
        business_confidence=_confidence_label(scores["ip_watch_priority"]["score"]),
        business_score=scores["ip_watch_priority"]["score"],
        evidence_basis=scores["ip_watch_priority"]["reasons"],
        web_signal_count=scores["web_signal_strength"]["web_signal_count"],
        business_signal_count=scores["web_signal_strength"]["business_signal_count"],
        technical_confidence=tech_conf,
        technical_score=float(tech_score) if tech_score not in (None, "") else None,
        uncertainty="This is not a legal validity or infringement assessment.",
        recommended_action="Monitor assignee activity and related filings in the same cluster.",
        recommended_reader_action="monitor_company_signals",
        caveat="IP watch priority is a screening signal for SMEs, not legal advice.",
      ).to_dict(),
    )

  sme = scores["sme_entry_opportunity"]
  if sme["score"] >= 0.35:
    items.append(
      BusinessAssessmentItem(
        publication_number=publication_number,
        patent_title=patent_title,
        assignee=assignee,
        primary_cluster_id=cluster_id,
        primary_cluster_name=cluster_name,
        business_topic="SME opportunity",
        assessment_type="sme_entry_opportunity",
        assessment=_sanitize_wording(
          "This area may offer SME entry, partnership, or verification candidate rather than direct head-on competition.",
        ),
        business_confidence=_confidence_label(sme["score"]),
        business_score=sme["score"],
        evidence_basis=sme["reasons"],
        web_signal_count=scores["web_signal_strength"]["web_signal_count"],
        technical_confidence=tech_conf,
        uncertainty="Entry opportunity candidates require customer and technical validation.",
        recommended_action="Explore niche application, evaluation method, or process-support positioning.",
        recommended_reader_action="explore_partnership_or_customer_need",
        caveat="SME opportunity is a candidate area, not a guaranteed market opening.",
      ).to_dict(),
    )

  design = scores["design_around_opportunity"]
  if design["score"] >= 0.35:
    items.append(
      BusinessAssessmentItem(
        publication_number=publication_number,
        patent_title=patent_title,
        assignee=assignee,
        primary_cluster_id=cluster_id,
        primary_cluster_name=cluster_name,
        business_topic="design-around / differentiation",
        assessment_type="design_around_opportunity",
        assessment="Technical uncertainty or evidence gaps may leave room for design-around or differentiation candidates.",
        business_confidence=_confidence_label(design["score"]),
        business_score=design["score"],
        evidence_basis=design["reasons"],
        technical_confidence=tech_conf,
        uncertainty="Design-around candidates require claim charting and expert review.",
        recommended_action="Review claim scope, examples, and alternative process routes.",
        recommended_reader_action="investigate_design_around",
        caveat="Differentiation candidate does not imply freedom to operate.",
      ).to_dict(),
    )

  for link in related_web_links:
    signal_type = str(link.get("signal_type") or "")
    if signal_type in STRONG_SIGNAL_TYPES and link.get("relation") == "business_signal_candidate":
      assessment_type = "investment_or_scaleup_signal"
      if signal_type in {"partnership", "joint_development", "customer_adoption"}:
        assessment_type = "partnership_or_customer_signal"
      items.append(
        BusinessAssessmentItem(
          publication_number=publication_number,
          patent_title=patent_title,
          assignee=assignee,
          primary_cluster_id=cluster_id,
          primary_cluster_name=cluster_name,
          business_topic=str(link.get("source_title", ""))[:80],
          assessment_type=assessment_type,
          assessment=f"Company activity signal candidate: {signal_type}",
          business_confidence=_confidence_label(scores["company_activity"]["score"]),
          business_score=scores["company_activity"]["score"],
          evidence_basis=[link.get("relation_reason", ""), f"signal_type={signal_type}"],
          web_signal_count=1,
          business_signal_count=1 if link.get("relation") == "business_signal_candidate" else 0,
          technical_confidence=tech_conf,
          uncertainty="Signal may be company-wide and not patent-specific.",
          recommended_action="Read source title and verify technology overlap manually.",
          recommended_reader_action="manual_web_source_review_required",
          caveat=link.get("caveat", "Web signal candidate only."),
        ).to_dict(),
      )
      break

  if scores["technical_business_alignment"].get("human_review_required"):
    items.append(
      BusinessAssessmentItem(
        publication_number=publication_number,
        patent_title=patent_title,
        assignee=assignee,
        business_topic="human review",
        assessment_type="human_review_required",
        assessment="Business signals appear stronger than technical evidence; expert review is recommended before action.",
        business_confidence="low",
        business_score=scores["overall"]["overall_score"],
        evidence_basis=scores["technical_business_alignment"]["reasons"],
        uncertainty="Misalignment between business and technical screening needs human validation.",
        recommended_action="Assign business and technical reviewers before strategic action.",
        recommended_reader_action="expert_ip_review_required",
        caveat="Automated screening cannot replace expert judgment.",
      ).to_dict(),
    )

  if not items:
    items.append(
      BusinessAssessmentItem(
        publication_number=publication_number,
        patent_title=patent_title,
        assignee=assignee,
        primary_cluster_id=cluster_id,
        primary_cluster_name=cluster_name,
        business_topic="monitor only",
        assessment_type="monitor_only",
        assessment="Limited business signal evidence; monitor only at this stage.",
        business_confidence="low",
        business_score=scores["overall"]["overall_score"],
        evidence_basis=["No strong business web signals linked"],
        uncertainty="Absence of signals does not mean absence of commercial activity.",
        recommended_action="Continue periodic monitoring of assignee and cluster.",
        recommended_reader_action="monitor_only",
        caveat="Monitor-only status may change with new web signal input.",
      ).to_dict(),
    )

  return items


def build_business_summary(patent_business_assessment: dict[str, Any]) -> str:
  title = patent_business_assessment.get("patent_title") or patent_business_assessment.get("publication_number")
  confidence = patent_business_assessment.get("overall_business_confidence", "unknown")
  cluster = patent_business_assessment.get("primary_cluster_name") or patent_business_assessment.get("primary_cluster_id")
  commercial = patent_business_assessment.get("commercialization_signals", [])[:2]
  watch = patent_business_assessment.get("competitive_watch_points", [])[:1]

  parts = [
    f"This patent ({title}) in cluster {cluster} shows {confidence} preliminary business priority as a screening result.",
    "Technical and web/company signal inputs were combined, but web signals are company-level candidates and do not prove implementation of this patent.",
  ]
  if commercial:
    parts.append(f"Commercialization signal candidates include: {'; '.join(commercial)}.")
  if watch:
    parts.append(f"Competitive watch points include: {'; '.join(watch)}.")
  parts.append("Claims, examples, and source URLs should be checked before any business action.")
  return _sanitize_wording(" ".join(parts))


def recommend_business_reader_action(patent_business_assessment: dict[str, Any]) -> str:
  action = patent_business_assessment.get("recommended_reader_action")
  if action:
    return action
  confidence = patent_business_assessment.get("overall_business_confidence", "unknown")
  if any(item.get("assessment_type") == "human_review_required" for item in patent_business_assessment.get("assessment_items", [])):
    return "expert_ip_review_required"
  if confidence == "high":
    return "monitor_company_signals"
  if patent_business_assessment.get("sme_opportunity_points"):
    return "explore_partnership_or_customer_need"
  if patent_business_assessment.get("design_around_or_differentiation_hints"):
    return "investigate_design_around"
  return "read_patent_and_examples_first"


def assess_patent_business_view(
  patent: dict[str, Any] | None,
  technical_summary: dict[str, Any] | None,
  technical_assessment: dict[str, Any] | None,
  related_web_links: list[dict[str, Any]],
  patent_evidence_map: dict[str, Any] | None = None,
) -> dict[str, Any]:
  patent = patent or {}
  technical_summary = technical_summary or {}
  if technical_assessment:
    technical_summary = {
      **technical_summary,
      "overall_technical_confidence": technical_assessment.get("overall_technical_confidence"),
      "overall_technical_score": technical_assessment.get("overall_technical_score"),
      "weak_or_uncertain_points": technical_assessment.get("weak_or_uncertain_points", []),
      "key_evidence_gaps": technical_assessment.get("key_evidence_gaps", []),
      "recommended_reader_action": technical_assessment.get("recommended_reader_action"),
    }

  publication_number = str(
    patent.get("publication_number")
    or technical_summary.get("publication_number")
    or (technical_assessment.get("publication_number") if technical_assessment else "")
    or ""
  )
  assessment_items = generate_business_assessment_items(patent, technical_summary, related_web_links)

  scores = {
    "web_signal_strength": score_web_signal_strength(related_web_links),
    "company_activity": score_company_activity(related_web_links),
    "technical_business_alignment": score_technical_business_alignment(technical_summary, related_web_links),
    "ip_watch_priority": score_ip_watch_priority(patent, technical_summary, related_web_links),
    "sme_entry_opportunity": score_sme_entry_opportunity(patent, technical_summary, related_web_links),
    "design_around_opportunity": score_design_around_opportunity(
      technical_summary,
      (patent_evidence_map or {}).get("key_evidence_gaps"),
      patent,
    ),
  }
  scores["overall"] = score_overall_business_confidence(scores)
  reader_action = classify_business_action(scores)

  commercialization = [
    item["assessment"] for item in assessment_items if item.get("assessment_type") == "commercialization_signal"
  ]
  competitive_watch = [
    item["assessment"] for item in assessment_items if item.get("assessment_type") in {"ip_watch_priority", "competitive_watch"}
  ]
  sme_points = [
    item["assessment"] for item in assessment_items if item.get("assessment_type") == "sme_entry_opportunity"
  ]
  design_hints = [
    item["assessment"] for item in assessment_items if item.get("assessment_type") == "design_around_opportunity"
  ]
  partnership_hints = [
    item["assessment"] for item in assessment_items if item.get("assessment_type") == "partnership_or_customer_signal"
  ]
  business_risks = []
  if scores["technical_business_alignment"].get("human_review_required"):
    business_risks.append("Business signals may outpace technical evidence confirmation.")
  if scores["sme_entry_opportunity"].get("opportunity_type") == "watch_avoid_or_partner":
    business_risks.append("Core manufacturing area may be difficult for direct SME entry.")

  recommended_actions = list({
    item.get("recommended_action") for item in assessment_items if item.get("recommended_action")
  })

  assessment = PatentBusinessAssessment(
    publication_number=publication_number,
    patent_title=patent.get("title") or patent.get("patent_title") or technical_summary.get("patent_title"),
    assignee=patent.get("assignee") or technical_summary.get("assignee"),
    primary_cluster_id=patent.get("primary_cluster_id"),
    primary_cluster_name=patent.get("primary_cluster_name"),
    overall_business_score=scores["overall"]["overall_score"],
    overall_business_confidence=scores["overall"]["overall_confidence"],
    commercialization_signals=commercialization,
    competitive_watch_points=competitive_watch,
    sme_opportunity_points=sme_points,
    design_around_or_differentiation_hints=design_hints,
    partnership_or_customer_hints=partnership_hints,
    business_risks=business_risks,
    recommended_next_actions=recommended_actions[:6],
    recommended_reader_action=reader_action,
    assessment_items=[BusinessAssessmentItem.from_dict(item) for item in assessment_items],
    caveats=[
      "Business assessment is preliminary intelligence, not legal or commercial proof.",
      "Web signals are company-level candidates and may not map to this patent.",
      "Patent validity, infringement, and FTO are out of scope.",
    ],
  )
  result = assessment.to_dict()
  result["business_summary"] = build_business_summary(result)
  result["recommended_reader_action"] = recommend_business_reader_action(result)
  if scores["overall"].get("human_review_required"):
    result["recommended_reader_action"] = "expert_ip_review_required"
  return result


def run_business_view_assessment(
  technical_assessments: list[dict[str, Any]],
  patent_technical_summary: list[dict[str, Any]],
  web_signal_links: list[dict[str, Any]],
  ranked_patents: list[dict[str, Any]] | None = None,
  patent_evidence_maps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
  warnings: list[str] = []
  errors: list[str] = []

  tech_by_pub = {str(row.get("publication_number")): row for row in patent_technical_summary}
  assessment_by_pub = {str(row.get("publication_number")): row for row in technical_assessments}
  patent_by_pub = {str(row.get("publication_number")): row for row in (ranked_patents or [])}
  evidence_by_pub = {str(row.get("publication_number")): row for row in (patent_evidence_maps or [])}

  links_by_pub: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for link in web_signal_links:
    links_by_pub[str(link.get("publication_number"))].append(link)

  publication_numbers = sorted(
    set(tech_by_pub) | set(assessment_by_pub) | set(links_by_pub) | set(patent_by_pub),
  )

  business_assessments: list[dict[str, Any]] = []
  all_items: list[dict[str, Any]] = []
  sme_candidates: list[dict[str, Any]] = []
  design_around_candidates: list[dict[str, Any]] = []

  for publication_number in publication_numbers:
    assessment = assess_patent_business_view(
      patent_by_pub.get(publication_number, {"publication_number": publication_number}),
      tech_by_pub.get(publication_number, {"publication_number": publication_number}),
      assessment_by_pub.get(publication_number),
      links_by_pub.get(publication_number, []),
      evidence_by_pub.get(publication_number),
    )
    business_assessments.append(assessment)
    all_items.extend(assessment.get("assessment_items", []))
    if assessment.get("sme_opportunity_points"):
      sme_candidates.append(
        {
          "publication_number": publication_number,
          "patent_title": assessment.get("patent_title"),
          "points": assessment.get("sme_opportunity_points"),
          "overall_business_confidence": assessment.get("overall_business_confidence"),
        },
      )
    if assessment.get("design_around_or_differentiation_hints"):
      design_around_candidates.append(
        {
          "publication_number": publication_number,
          "patent_title": assessment.get("patent_title"),
          "hints": assessment.get("design_around_or_differentiation_hints"),
          "overall_business_confidence": assessment.get("overall_business_confidence"),
        },
      )

  confidence_counter = Counter(a.get("overall_business_confidence") for a in business_assessments)
  signal_counter = Counter(item.get("assessment_type") for item in all_items)
  risk_counter = Counter(risk for assessment in business_assessments for risk in assessment.get("business_risks", []))

  return {
    "status": "ok",
    "total_patents": len(business_assessments),
    "business_assessments": business_assessments,
    "assessment_items": all_items,
    "high_business_priority_patents": confidence_counter.get("high", 0),
    "medium_business_priority_patents": confidence_counter.get("medium", 0),
    "low_business_priority_patents": confidence_counter.get("low", 0),
    "monitor_only_patents": sum(
      1 for assessment in business_assessments
      if assessment.get("recommended_reader_action") == "monitor_only"
    ),
    "expert_review_required": sum(
      1 for assessment in business_assessments
      if assessment.get("recommended_reader_action") == "expert_ip_review_required"
    ),
    "common_business_signals": dict(signal_counter),
    "common_business_risks": dict(risk_counter),
    "sme_opportunity_candidates": sme_candidates,
    "design_around_candidates": design_around_candidates,
    "warnings": warnings,
    "errors": errors,
  }
