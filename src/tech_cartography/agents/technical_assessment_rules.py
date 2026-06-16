"""Rule-based technical assessment scoring."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from typing import Any

SUPPORTING_RELATIONS = {"strong_evidence_candidate", "supporting_evidence_candidate"}
BACKGROUND_RELATIONS = {"background_evidence"}
WEAK_RELATIONS = {"weak_match"}
STRONG_CLAIM_SUPPORT = {"supported_by_examples", "supported_by_measured_properties"}
DESCRIPTION_SUPPORT = {"supported_by_description", *STRONG_CLAIM_SUPPORT}
MATERIAL_TERMS = {"pan", "polyacrylonitrile", "carbon fiber", "precursor", "resin", "炭素繊維", "前駆体"}
PROCESS_TERMS = {"carbonization", "stabilization", "surface treatment", "炭化", "表面処理", "耐炎化"}
PROPERTY_TERMS = {"tensile strength", "modulus", "adhesion", "引張強度", "弾性率"}
NUMERICAL_PATTERN = re.compile(
  r"\d+(?:\.\d+)?\s*(?:to|~|〜|-)?\s*\d*(?:\.\d+)?\s*(?:°|℃|C|GPa|MPa|min|wt%|%|Pa)",
  re.IGNORECASE,
)


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


def _items_from_patent_map(patent_map: dict[str, Any]) -> list[dict[str, Any]]:
  items = patent_map.get("evidence_items", [])
  return [item if isinstance(item, dict) else item.to_dict() for item in items]


def _count_relations(items: list[dict[str, Any]]) -> Counter:
  return Counter(str(item.get("evidence_relation")) for item in items)


def _count_support_status(items: list[dict[str, Any]]) -> Counter:
  return Counter(str(item.get("claim_support_status", "unclear")) for item in items)


def score_evidence_strength(patent_map: dict[str, Any]) -> dict[str, Any]:
  items = _items_from_patent_map(patent_map)
  relations = _count_relations(items)
  supporting = sum(relations.get(rel, 0) for rel in SUPPORTING_RELATIONS)
  background = relations.get("background_evidence", 0)
  weak = relations.get("weak_match", 0)
  no_paper = relations.get("no_paper_evidence", 0)
  high_quality = sum(1 for item in items if item.get("source_quality_level") == "high")

  score = 0.35
  reasons: list[str] = []
  if supporting:
    score += min(0.35, 0.08 * supporting)
    reasons.append(f"{supporting} supporting evidence candidate(s)")
  if high_quality:
    score += min(0.15, 0.05 * high_quality)
    reasons.append(f"{high_quality} high-quality source(s)")
  if background and not supporting:
    score += 0.08
    reasons.append("background evidence only")
  if weak and not supporting:
    score -= 0.08
    reasons.append("weak match evidence present")
  if no_paper:
    score -= min(0.25, 0.05 * no_paper)
    reasons.append(f"{no_paper} claim element(s) without paper evidence")

  return {
    "score": round(max(0.0, min(1.0, score)), 3),
    "reasons": reasons,
    "supporting_count": supporting,
    "background_count": background,
    "no_paper_count": no_paper,
  }


def score_description_support(patent_map: dict[str, Any]) -> dict[str, Any]:
  items = _items_from_patent_map(patent_map)
  support = _count_support_status(items)
  examples = support.get("supported_by_examples", 0)
  measured = support.get("supported_by_measured_properties", 0)
  description = support.get("supported_by_description", 0)
  claim_only = support.get("claim_only", 0)

  score = 0.3
  reasons: list[str] = []
  if examples:
    score += min(0.25, 0.1 * examples)
    reasons.append("examples support present")
  if measured:
    score += min(0.2, 0.08 * measured)
    reasons.append("measured properties support present")
  if description:
    score += min(0.15, 0.05 * description)
    reasons.append("description support present")
  if claim_only:
    score -= min(0.2, 0.05 * claim_only)
    reasons.append(f"{claim_only} claim-only element(s)")

  return {
    "score": round(max(0.0, min(1.0, score)), 3),
    "reasons": reasons,
    "examples_count": examples,
    "measured_count": measured,
    "claim_only_count": claim_only,
  }


def score_example_support(patent_map: dict[str, Any]) -> dict[str, Any]:
  result = score_description_support(patent_map)
  examples = result.get("examples_count", 0)
  score = 0.2 + min(0.5, 0.15 * examples)
  return {
    "score": round(max(0.0, min(1.0, score)), 3),
    "reasons": result.get("reasons", []),
    "examples_count": examples,
  }


def score_claim_only_risk(patent_map: dict[str, Any], gaps: list[dict[str, Any]]) -> dict[str, Any]:
  items = _items_from_patent_map(patent_map)
  support = _count_support_status(items)
  claim_only = support.get("claim_only", 0)
  gap_types = Counter(str(gap.get("gap_type")) for gap in gaps)
  scope_gaps = gap_types.get("claim_only_no_description_support", 0) + gap_types.get("no_paper_found", 0)

  risk_score = 0.2
  reasons: list[str] = []
  if claim_only:
    risk_score += min(0.4, 0.08 * claim_only)
    reasons.append(f"{claim_only} claim-only element(s)")
  if scope_gaps:
    risk_score += min(0.3, 0.1 * scope_gaps)
    reasons.append(f"{scope_gaps} scope-related evidence gap(s)")

  return {
    "score": round(max(0.0, min(1.0, risk_score)), 3),
    "reasons": reasons,
    "claim_only_count": claim_only,
    "scope_gap_count": scope_gaps,
    "human_review_required": risk_score >= 0.45 or scope_gaps >= 1 or claim_only >= 2,
  }


def score_paper_support(patent_map: dict[str, Any]) -> dict[str, Any]:
  items = _items_from_patent_map(patent_map)
  relations = _count_relations(items)
  supporting = sum(relations.get(rel, 0) for rel in SUPPORTING_RELATIONS)
  low_quality_only = all(
    item.get("source_quality_level") in {"low", "unknown", None}
    for item in items
    if item.get("evidence_relation") in SUPPORTING_RELATIONS
  ) if supporting else False

  score = 0.25
  reasons: list[str] = []
  if supporting:
    score += min(0.4, 0.1 * supporting)
    reasons.append("paper supporting evidence candidates present")
  if low_quality_only and supporting:
    score -= 0.15
    reasons.append("supporting papers have low source quality only")
  if relations.get("no_paper_evidence", 0) > len(items) / 2:
    score -= 0.1
    reasons.append("majority of elements lack paper evidence")

  return {
    "score": round(max(0.0, min(1.0, score)), 3),
    "reasons": reasons,
    "low_quality_only": low_quality_only,
    "supporting_count": supporting,
  }


def score_measurement_support(patent_map: dict[str, Any]) -> dict[str, Any]:
  items = _items_from_patent_map(patent_map)
  property_items = [item for item in items if item.get("element_type") == "property"]
  numerical_items = [item for item in items if item.get("element_type") == "numerical_condition"]
  measured_support = sum(
    1 for item in items if item.get("claim_support_status") == "supported_by_measured_properties"
  )
  eval_items = [item for item in items if item.get("element_type") == "evaluation_method"]

  score = 0.3
  reasons: list[str] = []
  if measured_support:
    score += min(0.3, 0.1 * measured_support)
    reasons.append("measured property support in patent text")
  if eval_items:
    score += 0.1
    reasons.append("evaluation method elements present")
  if property_items and not measured_support and not eval_items:
    score -= 0.15
    reasons.append("property claims without measurement support")
  if numerical_items:
    linked = sum(
      1 for item in numerical_items
      if item.get("claim_support_status") in STRONG_CLAIM_SUPPORT
    )
    if linked:
      score += 0.1
      reasons.append("numerical conditions linked to examples/measurements")
    else:
      score -= 0.1
      reasons.append("numerical conditions appear claim-only")

  return {
    "score": round(max(0.0, min(1.0, score)), 3),
    "reasons": reasons,
    "numerical_count": len(numerical_items),
    "property_without_measurement": bool(property_items and not measured_support),
  }


def score_implementation_risk(patent_map: dict[str, Any]) -> dict[str, Any]:
  items = _items_from_patent_map(patent_map)
  process_items = [item for item in items if item.get("element_type") == "process"]
  surface_items = [
    item for item in items
    if "surface" in str(item.get("element_text", "")).lower()
    or "interface" in str(item.get("element_text", "")).lower()
  ]
  application_only = all(item.get("element_type") == "application" for item in items) if items else False

  risk_score = 0.2
  reasons: list[str] = []
  weak_process = [
    item for item in process_items
    if item.get("claim_support_status") not in STRONG_CLAIM_SUPPORT
  ]
  if weak_process:
    risk_score += min(0.25, 0.08 * len(weak_process))
    reasons.append("process elements with weak example/measurement support")

  weak_surface = [
    item for item in surface_items
    if item.get("element_type") != "evaluation_method"
    and item.get("claim_support_status") not in STRONG_CLAIM_SUPPORT
  ]
  if weak_surface:
    risk_score += 0.15
    reasons.append("surface/interface elements without strong validation support")

  if application_only:
    risk_score += 0.1
    reasons.append("application-focused with limited material/process backing")

  return {
    "score": round(max(0.0, min(1.0, risk_score)), 3),
    "reasons": reasons,
    "process_risk_count": len(weak_process),
    "surface_risk_count": len(weak_surface),
  }


def score_material_process_property_linkage(patent_map: dict[str, Any]) -> dict[str, Any]:
  items = _items_from_patent_map(patent_map)
  types_present = {str(item.get("element_type")) for item in items}
  terms_text = " ".join(
    " ".join(_parse_terms(item.get("normalized_terms")))
    for item in items
  ).lower()

  has_material = "material" in types_present or any(term in terms_text for term in MATERIAL_TERMS)
  has_process = "process" in types_present or any(term in terms_text for term in PROCESS_TERMS)
  has_property = "property" in types_present or any(term in terms_text for term in PROPERTY_TERMS)

  score = 0.25
  reasons: list[str] = []
  if has_material and has_process and has_property:
    score += 0.35
    reasons.append("material + process + property linkage present")
  elif sum([has_material, has_process, has_property]) == 2:
    score += 0.15
    reasons.append("partial material/process/property linkage")
  elif has_material or has_process or has_property:
    score += 0.05
    reasons.append("single technical dimension only")
  else:
    reasons.append("limited material/process/property linkage")

  return {
    "score": round(max(0.0, min(1.0, score)), 3),
    "reasons": reasons,
    "has_material": has_material,
    "has_process": has_process,
    "has_property": has_property,
  }


def score_overall_technical_confidence(scores: dict[str, Any]) -> dict[str, Any]:
  positive = (
    scores.get("evidence_strength", {}).get("score", 0.0) * 0.25
    + scores.get("description_support", {}).get("score", 0.0) * 0.2
    + scores.get("paper_support", {}).get("score", 0.0) * 0.15
    + scores.get("measurement_support", {}).get("score", 0.0) * 0.15
    + scores.get("material_process_property", {}).get("score", 0.0) * 0.15
  )
  risk = (
    scores.get("claim_only_risk", {}).get("score", 0.0) * 0.15
    + scores.get("implementation_risk", {}).get("score", 0.0) * 0.15
  )
  overall = max(0.0, min(1.0, positive - risk * 0.5 + 0.15))

  if scores.get("paper_support", {}).get("low_quality_only"):
    overall = min(overall, 0.65)

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
    "human_review_required": scores.get("claim_only_risk", {}).get("human_review_required", False)
    or overall < 0.35,
  }
