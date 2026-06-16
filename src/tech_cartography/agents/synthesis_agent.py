"""Synthesis agent for Carbon Fiber Evidence Map report."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from tech_cartography.agents.synthesis_rules import (
  assign_synthesis_confidence,
  assign_synthesis_importance,
  build_global_caveats,
  select_priority_patents,
  synthesize_cluster_signals,
  synthesize_evidence_strength,
  synthesize_monitoring_recommendations,
  synthesize_sme_action_plan,
)
from tech_cartography.domain.synthesis_report import SynthesisFinding, SynthesisReport

FORBIDDEN_ASSERTIONS = (
  "事業化を証明",
  "参入できる",
  "商用化済み",
  "直接証明",
  "proven commercialization",
  "can enter the market",
  "directly proves",
)


def _sanitize_wording(text: str) -> str:
  sanitized = text
  replacements = {
    "事業化を証明": "事業化シグナル候補がある",
    "参入できる": "参入余地候補がある",
    "商用化済み": "商用化候補の兆候がある",
    "直接証明": "直接の証明ではなくEvidence Candidate",
    "proven commercialization": "commercialization signal candidates exist",
    "can enter the market": "may offer SME entry candidate",
    "directly proves": "may support as evidence candidate",
  }
  for old, new in replacements.items():
    sanitized = sanitized.replace(old, new)
  return sanitized


def build_key_findings(synthesis_inputs: dict[str, Any]) -> list[dict[str, Any]]:
  findings: list[SynthesisFinding] = []
  finding_index = 1

  for patent in synthesis_inputs.get("priority_patents", [])[:5]:
    findings.append(
      SynthesisFinding(
        finding_id=f"F{finding_index:03d}",
        finding_type="priority_patent",
        title=f"Priority patent candidate: {patent.get('publication_number')}",
        summary=_sanitize_wording(
          f"{patent.get('title') or patent.get('publication_number')} is a priority read candidate "
          f"because {patent.get('why_read', 'ranking and screening scores')}.",
        ),
        importance=patent.get("importance", assign_synthesis_importance(patent)),
        confidence=patent.get("confidence", assign_synthesis_confidence(patent)),
        related_publications=[str(patent.get("publication_number", ""))],
        related_companies=[str(patent.get("assignee"))] if patent.get("assignee") else [],
        related_clusters=[str(patent.get("primary_cluster_id"))] if patent.get("primary_cluster_id") else [],
        evidence_basis=[patent.get("why_read", "")],
        caveats=["Priority patent is a screening candidate, not legal or commercial proof."],
        recommended_next_action=str(patent.get("next_check", "read_patent_and_examples_first")),
      ),
    )
    finding_index += 1

  for cluster in synthesis_inputs.get("technology_cluster_summary", []):
    if "注目クラスタ" not in cluster.get("categories", []):
      continue
    findings.append(
      SynthesisFinding(
        finding_id=f"F{finding_index:03d}",
        finding_type="technology_cluster_signal",
        title=f"Attention cluster: {cluster.get('name')}",
        summary=_sanitize_wording(
          f"Cluster {cluster.get('name')} has {cluster.get('patent_count', 0)} patents and "
          f"{cluster.get('technical_signal', 'technical signals')}."
        ),
        importance="medium",
        confidence="medium",
        related_clusters=[str(cluster.get("cluster_id", ""))],
        related_publications=list(cluster.get("representative_patents", [])[:3]),
        related_companies=list(cluster.get("top_assignees", [])[:3]),
        evidence_basis=[cluster.get("technical_signal", ""), cluster.get("business_signal", "")],
        caveats=["Cluster grouping is rule-based and needs human validation."],
        recommended_next_action=cluster.get("next_action", "read representative patents"),
      ),
    )
    finding_index += 1

  claim_summary = synthesis_inputs.get("claim_paper_summary") or {}
  if claim_summary.get("supporting_evidence_candidates", 0) > 0:
    findings.append(
      SynthesisFinding(
        finding_id=f"F{finding_index:03d}",
        finding_type="paper_supported_claim_candidate",
        title="Paper evidence candidates linked to claim elements",
        summary=_sanitize_wording(
          f"{claim_summary.get('supporting_evidence_candidates', 0)} supporting paper evidence candidate(s) "
          "were found across mapped claim elements.",
        ),
        importance="medium",
        confidence="medium",
        evidence_basis=[
          f"supporting_evidence_candidates={claim_summary.get('supporting_evidence_candidates', 0)}",
          f"background_evidence={claim_summary.get('background_evidence', 0)}",
        ],
        caveats=["OpenAlex papers are evidence candidates, not direct proof of patent claims."],
        recommended_next_action="verify claim element wording against linked paper abstracts",
      ),
    )
    finding_index += 1

  for patent in synthesis_inputs.get("priority_patents", []):
    if not patent.get("human_review_required"):
      continue
    findings.append(
      SynthesisFinding(
        finding_id=f"F{finding_index:03d}",
        finding_type="human_review_required",
        title=f"Human review recommended: {patent.get('publication_number')}",
        summary=_sanitize_wording(
          f"Patent {patent.get('publication_number')} has {patent.get('evidence_gap_count', 0)} evidence gap(s) "
          "or screening misalignment requiring expert review.",
        ),
        importance="high",
        confidence="low",
        related_publications=[str(patent.get("publication_number", ""))],
        evidence_basis=[f"evidence_gap_count={patent.get('evidence_gap_count', 0)}"],
        caveats=["Automated screening cannot replace expert IP or technical review."],
        recommended_next_action="expert_ip_review_required",
      ),
    )
    finding_index += 1
    break

  for assessment in synthesis_inputs.get("business_assessments", []):
    if not assessment.get("commercialization_signals"):
      continue
    findings.append(
      SynthesisFinding(
        finding_id=f"F{finding_index:03d}",
        finding_type="business_signal_candidate",
        title=f"Business signal candidate: {assessment.get('publication_number')}",
        summary=_sanitize_wording(
          f"Web/company signal candidates overlap with {assessment.get('publication_number')} screening context.",
        ),
        importance=assign_synthesis_importance(
          {"priority_score": assessment.get("overall_business_score", 0.0)},
        ),
        confidence=str(assessment.get("overall_business_confidence", "unknown")),
        related_publications=[str(assessment.get("publication_number", ""))],
        related_companies=[str(assessment.get("assignee"))] if assessment.get("assignee") else [],
        related_clusters=[str(assessment.get("primary_cluster_id"))] if assessment.get("primary_cluster_id") else [],
        evidence_basis=assessment.get("commercialization_signals", [])[:2],
        caveats=["Web signals are company-level business context candidates, not patent implementation proof."],
        recommended_next_action=assessment.get("recommended_reader_action", "monitor_company_signals"),
      ),
    )
    finding_index += 1
    break

  for assessment in synthesis_inputs.get("business_assessments", []):
    if not assessment.get("sme_opportunity_points"):
      continue
    findings.append(
      SynthesisFinding(
        finding_id=f"F{finding_index:03d}",
        finding_type="sme_opportunity_candidate",
        title=f"SME opportunity candidate: {assessment.get('publication_number')}",
        summary=_sanitize_wording(
          "Adjacent application, evaluation, or process-support positioning may offer SME entry candidate.",
        ),
        importance="medium",
        confidence="low",
        related_publications=[str(assessment.get("publication_number", ""))],
        evidence_basis=assessment.get("sme_opportunity_points", [])[:2],
        caveats=["SME opportunity is a candidate area, not a guaranteed market opening."],
        recommended_next_action="explore_partnership_or_customer_need",
      ),
    )
    finding_index += 1
    break

  for assessment in synthesis_inputs.get("business_assessments", []):
    if not assessment.get("design_around_or_differentiation_hints"):
      continue
    findings.append(
      SynthesisFinding(
        finding_id=f"F{finding_index:03d}",
        finding_type="design_around_candidate",
        title=f"Design-around candidate: {assessment.get('publication_number')}",
        summary=_sanitize_wording(
          "Technical uncertainty or evidence gaps may leave room for design-around or differentiation candidates.",
        ),
        importance="medium",
        confidence="low",
        related_publications=[str(assessment.get("publication_number", ""))],
        evidence_basis=assessment.get("design_around_or_differentiation_hints", [])[:2],
        caveats=["Differentiation candidate does not imply freedom to operate."],
        recommended_next_action="investigate_design_around",
      ),
    )
    finding_index += 1
    break

  gap_counter = Counter(str(gap.get("gap_type")) for gap in synthesis_inputs.get("evidence_gaps", []))
  if gap_counter:
    top_gap, count = gap_counter.most_common(1)[0]
    findings.append(
      SynthesisFinding(
        finding_id=f"F{finding_index:03d}",
        finding_type="evidence_gap",
        title=f"Evidence gap pattern: {top_gap}",
        summary=_sanitize_wording(
          f"{count} claim element(s) show gap type '{top_gap}' and need additional paper or description review.",
        ),
        importance="medium" if count >= 2 else "low",
        confidence="low",
        evidence_basis=[f"gap_type={top_gap}", f"count={count}"],
        caveats=["Evidence gaps indicate verification room, not absence of technology importance."],
        recommended_next_action="check_technical_evidence_before_action",
      ),
    )

  return [finding.to_dict() for finding in findings]


def build_evidence_based_action_plan(synthesis_inputs: dict[str, Any]) -> list[dict[str, Any]]:
  return synthesize_sme_action_plan(
    synthesis_inputs.get("priority_patents", []),
    synthesis_inputs.get("patent_business_summary", []),
    synthesis_inputs.get("patent_technical_summary", []),
    business_assessments=synthesis_inputs.get("business_assessments", []),
    web_signals_by_company=synthesis_inputs.get("web_signals_by_company"),
  )


def build_update_recommendations(synthesis_inputs: dict[str, Any]) -> list[str]:
  return synthesize_monitoring_recommendations(
    synthesis_inputs.get("cluster_summary", []),
    synthesis_inputs.get("evidence_gaps"),
    synthesis_inputs.get("web_signals_by_cluster"),
    retrieval_summary=synthesis_inputs.get("retrieval_summary"),
  )


def build_executive_summary(synthesis: dict[str, Any]) -> str:
  theme = synthesis.get("theme", "PAN系炭素繊維")
  priority_count = len(synthesis.get("priority_patents", []))
  cluster_names = [
    cluster.get("name")
    for cluster in synthesis.get("technology_cluster_summary", [])[:3]
    if cluster.get("name")
  ]
  evidence = synthesis.get("evidence_strength_summary", {})
  business_high = synthesis.get("business_view_summary", {}).get("high_business_priority", 0)
  technical_high = synthesis.get("technical_view_summary", {}).get("high_confidence", 0)

  parts = [
    f"今回のCarbon Fiber Evidence Mapでは、{theme}をテーマに、"
    f"{', '.join(cluster_names) if cluster_names else '主要技術クラスタ'}周辺に重要候補が集まった。",
    f"Top20から優先読了候補を{priority_count}件選定し、"
    f"技術評価で中〜高confidenceが{technical_high}件、事業評価で高優先度が{business_high}件確認された。",
  ]
  if evidence.get("supporting_evidence_candidates"):
    parts.append(
      f"一部請求項要素には論文Evidence Candidateが{evidence.get('supporting_evidence_candidates')}件対応するが、"
      "論文は特許主張の直接証明ではない。",
    )
  if business_high:
    parts.append(
      "企業Webシグナル候補とも重なる領域があるため、請求項・実施例・関連論文の確認価値がある。"
    )
  parts.append(
    "Webシグナルは特定特許の実施を示すものではなく、人間による確認が必要である。"
  )
  return _sanitize_wording("".join(parts))


def run_synthesis_report(
  cluster_summary: list[dict[str, Any]],
  top20_patents: list[dict[str, Any]],
  top5_candidates: list[dict[str, Any]],
  technical_assessments: list[dict[str, Any]],
  patent_technical_summary: list[dict[str, Any]],
  business_assessments: list[dict[str, Any]],
  patent_business_summary: list[dict[str, Any]],
  retrieval_summary: dict[str, Any] | None = None,
  fulltext_summary: dict[str, Any] | None = None,
  claim_element_summary: dict[str, Any] | None = None,
  claim_paper_summary: dict[str, Any] | None = None,
  evidence_gaps: list[dict[str, Any]] | None = None,
  source_quality_results: list[dict[str, Any]] | None = None,
  web_signals_by_company: list[dict[str, Any]] | None = None,
  web_signals_by_cluster: list[dict[str, Any]] | None = None,
  theme: str = "PAN系炭素繊維",
) -> dict[str, Any]:
  warnings: list[str] = []
  errors: list[str] = []

  if not top20_patents:
    warnings.append("top20_patents is empty; priority patent list may be limited")
  if not patent_technical_summary:
    warnings.append("patent_technical_summary is empty")
  if not patent_business_summary:
    warnings.append("patent_business_summary is empty")

  priority_patents = select_priority_patents(
    top20_patents,
    patent_technical_summary,
    patent_business_summary,
    top5_candidates=top5_candidates,
    business_assessments=business_assessments,
    evidence_gaps=evidence_gaps,
  )
  technology_cluster_summary = synthesize_cluster_signals(
    cluster_summary,
    patent_technical_summary,
    patent_business_summary,
    web_signals_by_cluster=web_signals_by_cluster,
    evidence_gaps=evidence_gaps,
  )
  evidence_strength_summary = synthesize_evidence_strength(
    claim_paper_summary,
    source_quality_results,
    evidence_gaps,
  )

  tech_conf_counter = Counter(row.get("overall_technical_confidence") for row in patent_technical_summary)
  technical_view_summary = {
    "assessed_patents": len(technical_assessments) or len(patent_technical_summary),
    "high_confidence": tech_conf_counter.get("high", 0),
    "medium_confidence": tech_conf_counter.get("medium", 0),
    "low_confidence": tech_conf_counter.get("low", 0),
    "human_review_required": sum(
      1 for row in technical_assessments
      if row.get("recommended_reader_action") == "expert_review_required"
    ),
    "common_gaps": Counter(
      gap for row in patent_technical_summary for gap in row.get("key_evidence_gaps", [])
    ).most_common(5),
  }

  biz_conf_counter = Counter(row.get("overall_business_confidence") for row in patent_business_summary)
  business_view_summary = {
    "assessed_patents": len(business_assessments) or len(patent_business_summary),
    "high_business_priority": biz_conf_counter.get("high", 0),
    "medium_business_priority": biz_conf_counter.get("medium", 0),
    "low_business_priority": biz_conf_counter.get("low", 0),
    "sme_opportunity_count": sum(1 for row in business_assessments if row.get("sme_opportunity_points")),
    "design_around_count": sum(
      1 for row in business_assessments if row.get("design_around_or_differentiation_hints")
    ),
  }

  synthesis_inputs = {
    "cluster_summary": cluster_summary,
    "priority_patents": priority_patents,
    "technology_cluster_summary": technology_cluster_summary,
    "patent_technical_summary": patent_technical_summary,
    "patent_business_summary": patent_business_summary,
    "business_assessments": business_assessments,
    "claim_paper_summary": claim_paper_summary,
    "evidence_gaps": evidence_gaps or [],
    "web_signals_by_company": web_signals_by_company,
    "web_signals_by_cluster": web_signals_by_cluster,
    "retrieval_summary": retrieval_summary,
  }

  sme_action_plan = build_evidence_based_action_plan(synthesis_inputs)
  key_findings = build_key_findings(synthesis_inputs)
  next_update_recommendations = build_update_recommendations(synthesis_inputs)
  caveats = build_global_caveats()

  generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
  interim = {
    "theme": theme,
    "generated_at": generated_at,
    "priority_patents": priority_patents,
    "technology_cluster_summary": technology_cluster_summary,
    "evidence_strength_summary": evidence_strength_summary,
    "technical_view_summary": technical_view_summary,
    "business_view_summary": business_view_summary,
    "sme_action_plan": sme_action_plan,
    "evidence_gaps": evidence_gaps or [],
    "key_findings": key_findings,
    "next_update_recommendations": next_update_recommendations,
    "caveats": caveats,
  }
  executive_summary = build_executive_summary(interim)

  report = SynthesisReport(
    report_title="Carbon Fiber Evidence Map v1",
    theme=theme,
    generated_at=generated_at,
    executive_summary=executive_summary,
    key_findings=[SynthesisFinding.from_dict(item) for item in key_findings],
    priority_patents=priority_patents,
    technology_cluster_summary=technology_cluster_summary,
    evidence_strength_summary=evidence_strength_summary,
    technical_view_summary=technical_view_summary,
    business_view_summary=business_view_summary,
    sme_action_plan=sme_action_plan,
    evidence_gaps=evidence_gaps or [],
    caveats=caveats,
    next_update_recommendations=next_update_recommendations,
  )

  result = report.to_dict()
  result.update(
    {
      "status": "ok",
      "warnings": warnings,
      "errors": errors,
      "retrieval_summary": retrieval_summary or {},
      "fulltext_summary": fulltext_summary or {},
      "claim_element_summary": claim_element_summary or {},
      "claim_paper_summary": claim_paper_summary or {},
      "web_signals_by_company": web_signals_by_company or [],
      "web_signals_by_cluster": web_signals_by_cluster or [],
    },
  )
  return result
