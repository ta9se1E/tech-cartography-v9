"""Technical View Agent for patent technical assessment."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from typing import Any

from tech_cartography.agents.technical_assessment_rules import (
  NUMERICAL_PATTERN,
  STRONG_CLAIM_SUPPORT,
  SUPPORTING_RELATIONS,
  score_claim_only_risk,
  score_description_support,
  score_evidence_strength,
  score_implementation_risk,
  score_material_process_property_linkage,
  score_measurement_support,
  score_overall_technical_confidence,
  score_paper_support,
)
from tech_cartography.domain.technical_assessment import (
  PatentTechnicalAssessment,
  TechnicalAssessmentItem,
)

FORBIDDEN_ASSERTIONS = ("証明された", "証明済み", "妥当である", "確実に", "proven", "definitely valid")


def _parse_terms(value: Any) -> list[str]:
  if isinstance(value, list):
    return [str(item).strip() for item in value if str(item).strip()]
  if isinstance(value, str):
    text = value.strip()
    if not text:
      return []
    if text.startswith("["):
      try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
          return [str(item).strip() for item in parsed if str(item).strip()]
      except json.JSONDecodeError:
        pass
    return [part.strip() for part in re.split(r"[;,]", text) if part.strip()]
  return []


def _sanitize_wording(text: str) -> str:
  sanitized = text
  replacements = {
    "証明された": "支持候補がある",
    "証明済み": "支持候補がある",
    "妥当である": "妥当性を示す候補がある",
    "proven": "supporting evidence candidates exist",
    "definitely valid": "appears reasonably supported as a candidate",
  }
  for old, new in replacements.items():
    sanitized = sanitized.replace(old, new)
  return sanitized


def _items_from_map(patent_map: dict[str, Any]) -> list[dict[str, Any]]:
  items = patent_map.get("evidence_items", [])
  return [item if isinstance(item, dict) else item.to_dict() for item in items]


def _confidence_label(score: float) -> str:
  if score >= 0.7:
    return "high"
  if score >= 0.45:
    return "medium"
  if score >= 0.2:
    return "low"
  return "unknown"


def generate_technical_assessment_items(
  patent_map: dict[str, Any],
  related_items: list[dict[str, Any]],
  related_gaps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
  publication_number = str(patent_map.get("publication_number"))
  patent_title = patent_map.get("patent_title")
  assignee = patent_map.get("assignee")
  items = related_items or _items_from_map(patent_map)
  gaps_by_element = defaultdict(list)
  for gap in related_gaps:
    gaps_by_element[str(gap.get("element_id"))].append(gap)

  assessment_items: list[dict[str, Any]] = []
  scores = {
    "evidence_strength": score_evidence_strength(patent_map),
    "description_support": score_description_support(patent_map),
    "paper_support": score_paper_support(patent_map),
    "measurement_support": score_measurement_support(patent_map),
    "implementation_risk": score_implementation_risk(patent_map),
    "claim_only_risk": score_claim_only_risk(patent_map, related_gaps),
    "material_process_property": score_material_process_property_linkage(patent_map),
  }

  assessment_items.append(
    TechnicalAssessmentItem(
      publication_number=publication_number,
      patent_title=patent_title,
      assignee=assignee,
      element_id=None,
      element_type=None,
      technical_topic="overall evidence strength",
      assessment_type="evidence_strength",
      assessment=_sanitize_wording(
        "Patent claim elements show supporting evidence candidates based on mapped paper links and patent text support.",
      ),
      technical_confidence=_confidence_label(scores["evidence_strength"]["score"]),
      technical_score=scores["evidence_strength"]["score"],
      evidence_basis=scores["evidence_strength"]["reasons"],
      supporting_evidence_count=scores["evidence_strength"]["supporting_count"],
      background_evidence_count=scores["evidence_strength"]["background_count"],
      evidence_gap_count=len(related_gaps),
      uncertainty="Paper candidates do not prove patent claims.",
      recommended_check="Review top supporting paper candidates and claim element mapping.",
      recommended_reader_action="check_literature_before_action",
      caveat="Evidence strength reflects candidate alignment, not technical proof.",
    ).to_dict(),
  )

  if scores["claim_only_risk"]["score"] >= 0.45:
    assessment_items.append(
      TechnicalAssessmentItem(
        publication_number=publication_number,
        patent_title=patent_title,
        assignee=assignee,
        technical_topic="claim scope coverage",
        assessment_type="claim_scope_risk",
        assessment=_sanitize_wording(
          "Several claim elements appear claim-only or weakly supported by description/examples, suggesting claim scope review is needed.",
        ),
        technical_confidence="low" if scores["claim_only_risk"]["score"] >= 0.6 else "medium",
        technical_score=1.0 - scores["claim_only_risk"]["score"],
        evidence_basis=scores["claim_only_risk"]["reasons"],
        evidence_gap_count=scores["claim_only_risk"]["scope_gap_count"],
        uncertainty="Claim breadth may exceed documented experimental support.",
        recommended_check="Compare independent claims with description, examples, and measured properties.",
        recommended_reader_action="read_claims_and_examples_first",
        caveat="Claim scope risk is a screening signal, not a legal invalidity judgment.",
      ).to_dict(),
    )

  if scores["implementation_risk"]["score"] >= 0.4:
    assessment_items.append(
      TechnicalAssessmentItem(
        publication_number=publication_number,
        patent_title=patent_title,
        assignee=assignee,
        technical_topic="implementation feasibility",
        assessment_type="implementation_risk",
        assessment="Process or interface-related elements may face implementation uncertainty without stronger example support.",
        technical_confidence="low" if scores["implementation_risk"]["score"] >= 0.6 else "medium",
        technical_score=1.0 - scores["implementation_risk"]["score"],
        evidence_basis=scores["implementation_risk"]["reasons"],
        uncertainty="Scale-up and manufacturing details may be under-documented.",
        recommended_check="Review examples, process conditions, and equipment details in the full text.",
        recommended_reader_action="check_examples_and_measured_properties",
        caveat="Implementation risk assessment is preliminary.",
      ).to_dict(),
    )

  if scores["measurement_support"].get("property_without_measurement"):
    assessment_items.append(
      TechnicalAssessmentItem(
        publication_number=publication_number,
        patent_title=patent_title,
        assignee=assignee,
        technical_topic="property validation",
        assessment_type="measurement_risk",
        assessment="Property-related claim elements may lack sufficient measurement or evaluation method support.",
        technical_confidence="low",
        technical_score=scores["measurement_support"]["score"],
        evidence_basis=scores["measurement_support"]["reasons"],
        uncertainty="Reported property values may not be fully traceable to examples.",
        recommended_check="Verify measured properties, test methods, and numerical conditions in examples.",
        recommended_reader_action="check_examples_and_measured_properties",
        caveat="Measurement risk does not deny the property claim; it flags verification needs.",
      ).to_dict(),
    )

  numerical_items = [item for item in items if item.get("element_type") == "numerical_condition"]
  for item in numerical_items[:3]:
    element_id = str(item.get("element_id"))
    has_example_link = item.get("claim_support_status") in STRONG_CLAIM_SUPPORT
    assessment_items.append(
      TechnicalAssessmentItem(
        publication_number=publication_number,
        patent_title=patent_title,
        assignee=assignee,
        element_id=element_id,
        element_type="numerical_condition",
        technical_topic=str(item.get("element_text", "numerical condition"))[:80],
        assessment_type="experiment_check",
        assessment=(
          "Numerical condition appears linked to examples or measurements."
          if has_example_link
          else "Numerical condition appears mainly in claims and needs example/measurement confirmation."
        ),
        technical_confidence="medium" if has_example_link else "low",
        technical_score=0.65 if has_example_link else 0.3,
        evidence_basis=[f"claim_support_status={item.get('claim_support_status')}"],
        evidence_gap_count=len(gaps_by_element.get(element_id, [])),
        uncertainty="Numerical ranges require cross-check with working examples.",
        recommended_check="Confirm temperature/time/tension/concentration values in examples and measured properties.",
        recommended_reader_action="check_examples_and_measured_properties",
        caveat="Numerical condition support is rule-based and requires human verification.",
      ).to_dict(),
    )

  if scores["material_process_property"]["score"] >= 0.5:
    assessment_items.append(
      TechnicalAssessmentItem(
        publication_number=publication_number,
        patent_title=patent_title,
        assignee=assignee,
        technical_topic="material-process-property linkage",
        assessment_type="feasibility_signal",
        assessment="Material, process, and property elements appear together, suggesting a more coherent technical story as a candidate.",
        technical_confidence=_confidence_label(scores["material_process_property"]["score"]),
        technical_score=scores["material_process_property"]["score"],
        evidence_basis=scores["material_process_property"]["reasons"],
        uncertainty="Coherence across elements does not guarantee manufacturability.",
        recommended_check="Trace each element from material selection through process to reported properties.",
        recommended_reader_action="read_claims_and_examples_first",
        caveat="Linkage scoring is heuristic.",
      ).to_dict(),
    )

  if scores["paper_support"].get("low_quality_only"):
    assessment_items.append(
      TechnicalAssessmentItem(
        publication_number=publication_number,
        patent_title=patent_title,
        assignee=assignee,
        technical_topic="literature support quality",
        assessment_type="literature_check",
        assessment="Supporting paper candidates exist but source quality is mostly low; confidence should remain limited.",
        technical_confidence="low",
        technical_score=scores["paper_support"]["score"],
        evidence_basis=scores["paper_support"]["reasons"],
        uncertainty="Low-quality bibliographic metadata limits literature screening confidence.",
        recommended_check="Manually verify DOI, journal, and abstract before using papers as background.",
        recommended_reader_action="check_literature_before_action",
        caveat="SourceQuality reflects reference usability, not paper correctness.",
      ).to_dict(),
    )

  if scores["claim_only_risk"].get("human_review_required"):
    assessment_items.append(
      TechnicalAssessmentItem(
        publication_number=publication_number,
        patent_title=patent_title,
        assignee=assignee,
        technical_topic="human review",
        assessment_type="human_review_required",
        assessment="Multiple evidence gaps or claim-only elements suggest expert review before technical action.",
        technical_confidence="low",
        technical_score=0.25,
        evidence_basis=scores["claim_only_risk"]["reasons"],
        evidence_gap_count=len(related_gaps),
        uncertainty="Automated screening cannot replace expert technical review.",
        recommended_check="Assign a domain expert to review claims, examples, and paper candidates.",
        recommended_reader_action="expert_review_required",
        caveat="Human review is recommended, not optional, for high-stakes decisions.",
      ).to_dict(),
    )

  return assessment_items


def build_technical_summary(patent_assessment: dict[str, Any]) -> str:
  title = patent_assessment.get("patent_title") or patent_assessment.get("publication_number")
  confidence = patent_assessment.get("overall_technical_confidence", "unknown")
  strongest = patent_assessment.get("strongest_supported_points", [])[:2]
  weak = patent_assessment.get("weak_or_uncertain_points", [])[:2]
  parts = [
    f"This patent ({title}) shows {confidence} preliminary technical confidence as a screening result.",
    "Some claim elements appear to have supporting evidence candidates in patent text and/or mapped literature.",
  ]
  if strongest:
    parts.append(f"Stronger candidate areas include: {'; '.join(strongest)}.")
  if weak:
    parts.append(f"Uncertain areas include: {'; '.join(weak)}.")
  parts.append(
    "Implementation feasibility should be judged only after reviewing examples, measured properties, and process conditions.",
  )
  summary = " ".join(parts)
  return _sanitize_wording(summary)


def recommend_reader_action(patent_assessment: dict[str, Any]) -> str:
  confidence = patent_assessment.get("overall_technical_confidence", "unknown")
  risks = patent_assessment.get("implementation_risks", [])
  gaps = patent_assessment.get("key_evidence_gaps", [])
  items = patent_assessment.get("assessment_items", [])
  actions = [str(item.get("recommended_reader_action")) for item in items if item.get("recommended_reader_action")]

  if any(action == "expert_review_required" for action in actions) or confidence == "low":
    return "expert_review_required"
  if any("claim_only" in gap.lower() or "no_paper" in gap.lower() for gap in gaps):
    return "read_claims_and_examples_first"
  if risks:
    return "check_examples_and_measured_properties"
  if confidence == "high":
    return "check_literature_before_action"
  if confidence == "medium":
    return "monitor_only"
  return "manual_fulltext_required"


def assess_patent_technical_view(
  patent_map: dict[str, Any],
  related_items: list[dict[str, Any]],
  related_gaps: list[dict[str, Any]],
  claim_elements: list[dict[str, Any]] | None = None,
  fulltext_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
  publication_number = str(patent_map.get("publication_number"))
  items = related_items or _items_from_map(patent_map)

  scores = {
    "evidence_strength": score_evidence_strength(patent_map),
    "description_support": score_description_support(patent_map),
    "paper_support": score_paper_support(patent_map),
    "measurement_support": score_measurement_support(patent_map),
    "implementation_risk": score_implementation_risk(patent_map),
    "claim_only_risk": score_claim_only_risk(patent_map, related_gaps),
    "material_process_property": score_material_process_property_linkage(patent_map),
  }
  overall = score_overall_technical_confidence(scores)
  assessment_items = generate_technical_assessment_items(patent_map, items, related_gaps)

  strongest: list[str] = []
  weak_points: list[str] = []
  for item in items:
    relation = str(item.get("evidence_relation"))
    text = str(item.get("element_text", ""))[:60]
    if relation in SUPPORTING_RELATIONS and item.get("source_quality_level") in {"high", "medium"}:
      strongest.append(f"{item.get('element_type')}: {text}")
    if relation in {"weak_match", "no_paper_evidence"} or item.get("claim_support_status") == "claim_only":
      weak_points.append(f"{item.get('element_type')}: {text}")

  key_gaps = [
    f"{gap.get('gap_type')}: {str(gap.get('element_text', ''))[:50]}"
    for gap in related_gaps[:5]
  ]
  implementation_risks = [
    item["assessment"] for item in assessment_items if item.get("assessment_type") == "implementation_risk"
  ]
  measurement_risks = [
    item["assessment"] for item in assessment_items if item.get("assessment_type") == "measurement_risk"
  ]
  recommended_checks = list({
    item.get("recommended_check")
    for item in assessment_items
    if item.get("recommended_check")
  })

  assessment = PatentTechnicalAssessment(
    publication_number=publication_number,
    patent_title=patent_map.get("patent_title"),
    assignee=patent_map.get("assignee"),
    overall_technical_score=overall["overall_score"],
    overall_technical_confidence=overall["overall_confidence"],
    technical_summary="",
    strongest_supported_points=strongest[:5],
    weak_or_uncertain_points=weak_points[:5],
    key_evidence_gaps=key_gaps,
    implementation_risks=implementation_risks,
    measurement_or_validation_risks=measurement_risks,
    recommended_next_checks=recommended_checks[:6],
    recommended_reader_action="",
    assessment_items=[TechnicalAssessmentItem.from_dict(item) for item in assessment_items],
    caveats=[
      "This is a preliminary technical screening assessment, not proof of validity.",
      "Paper candidates support background review only.",
      "Rule-based claim element extraction requires human confirmation.",
    ],
  )
  assessment_dict = assessment.to_dict()
  assessment_dict["technical_summary"] = build_technical_summary(assessment_dict)
  assessment_dict["recommended_reader_action"] = recommend_reader_action(assessment_dict)
  if overall.get("human_review_required"):
    assessment_dict["recommended_reader_action"] = "expert_review_required"
  return assessment_dict


def run_technical_view_assessment(
  patent_evidence_maps: list[dict[str, Any]],
  evidence_items: list[dict[str, Any]],
  evidence_gaps: list[dict[str, Any]],
  claim_elements: list[dict[str, Any]] | None = None,
  fulltext_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
  warnings: list[str] = []
  errors: list[str] = []

  items_by_patent: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for item in evidence_items:
    items_by_patent[str(item.get("publication_number"))].append(item)

  gaps_by_patent: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for gap in evidence_gaps:
    gaps_by_patent[str(gap.get("publication_number"))].append(gap)

  fulltext_by_patent = {
    str(record.get("publication_number")): record for record in (fulltext_records or [])
  }

  technical_assessments: list[dict[str, Any]] = []
  all_items: list[dict[str, Any]] = []

  for patent_map in patent_evidence_maps:
    publication_number = str(patent_map.get("publication_number"))
    related_items = items_by_patent.get(publication_number, _items_from_map(patent_map))
    related_gaps = gaps_by_patent.get(publication_number, [])
    assessment = assess_patent_technical_view(
      patent_map,
      related_items,
      related_gaps,
      claim_elements=claim_elements,
      fulltext_record=fulltext_by_patent.get(publication_number),
    )
    technical_assessments.append(assessment)
    all_items.extend(assessment.get("assessment_items", []))

  confidence_counter = Counter(a.get("overall_technical_confidence") for a in technical_assessments)
  risk_counter = Counter(
    item.get("assessment_type")
    for item in all_items
    if item.get("assessment_type") in {"implementation_risk", "measurement_risk", "claim_scope_risk"}
  )
  gap_counter = Counter(gap.get("gap_type") for gap in evidence_gaps)

  return {
    "status": "ok",
    "total_patents": len(technical_assessments),
    "technical_assessments": technical_assessments,
    "assessment_items": all_items,
    "high_confidence_patents": confidence_counter.get("high", 0),
    "medium_confidence_patents": confidence_counter.get("medium", 0),
    "low_confidence_patents": confidence_counter.get("low", 0),
    "human_review_required": sum(
      1 for assessment in technical_assessments
      if assessment.get("recommended_reader_action") == "expert_review_required"
    ),
    "common_technical_risks": dict(risk_counter),
    "common_evidence_gaps": dict(gap_counter),
    "warnings": warnings,
    "errors": errors,
  }
