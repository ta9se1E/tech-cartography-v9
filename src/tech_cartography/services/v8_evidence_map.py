"""v8 Evidence Map builder — rule-based claim-source linking (Phase 27F)."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from tech_cartography.runtime.v8_claim_map_schema import V8ClaimMap, V8ClaimRecord
from tech_cartography.runtime.v8_evidence_map_schema import (
  EVIDENCE_MAP_SAFETY_NOTICES,
  V8EvidenceLink,
  V8EvidenceMap,
)
from tech_cartography.runtime.v8_sources_schema import V8SourceRecord, V8SourcesTable, utc_now_iso
from tech_cartography.services.v8_claim_map import build_claim_map
from tech_cartography.services.v8_claim_map_export import find_latest_claim_map_dir
from tech_cartography.services.v8_sources_repository import load_sources_table
from tech_cartography.services.v8_sources_table import project_root_from_here

CASE_KEYWORDS: dict[str, tuple[str, ...]] = {
  "case_01_pan_graphitization": (
    "pan", "polyacrylonitrile", "precursor", "stabilization", "oxidation", "carbonization",
    "graphitization", "tensile strength", "modulus", "elongation", "fiber bundle",
    "process condition", "structure", "carbon fiber",
  ),
  "case_02_sizing_interface": (
    "sizing", "surface treatment", "coating", "interface", "interfacial", "adhesion",
    "matrix", "resin", "epoxy", "composite", "ilss", "shear strength",
  ),
  "case_03_pressure_vessel_filament_winding": (
    "pressure vessel", "hydrogen tank", "filament winding", "cfrp", "composite pressure vessel",
    "liner", "type iv", "burst", "fatigue", "hoop", "winding", "resin", "towpreg", "safety", "regulation",
  ),
}

EVIDENCE_NEEDED_TO_SUPPORT: dict[str, str] = {
  "example_support": "direct_example_candidate",
  "process_condition_support": "process_condition_candidate",
  "property_data_support": "property_data_candidate",
  "structure_characterization_support": "structure_characterization_candidate",
  "paper_support": "paper_support_candidate",
  "application_validation_support": "application_validation_support",
  "claim_text_loading_required": "claim_text_required",
}


def _link_id(case_id: str, claim_id: str, source_id: str, support_type: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{claim_id}|{source_id}|{support_type}".encode()).hexdigest()[:12]
  return f"{case_id}:evidence_link:{digest}"


def _map_id(case_id: str, publication_number: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{publication_number}|evidence_map".encode()).hexdigest()[:12]
  return f"{case_id}:evidence_map:{digest}"


def _source_blob(source: V8SourceRecord) -> str:
  return f"{source.title} {source.organization} {source.notes} {source.evidence_role}".lower()


def _claim_terms(claim: V8ClaimRecord) -> list[str]:
  terms: list[str] = []
  for bucket in (
    claim.technical_axis_labels,
    claim.material_terms,
    claim.process_terms,
    claim.property_terms,
    claim.structure_terms,
    claim.application_terms,
    claim.condition_terms,
    claim.evidence_needed,
  ):
    terms.extend(bucket)
  return [t for t in terms if t]


def _matched_terms(claim: V8ClaimRecord, source: V8SourceRecord, case_id: str) -> list[str]:
  blob = _source_blob(source)
  hits: list[str] = []
  for term in _claim_terms(claim):
    if term and term.lower() in blob:
      hits.append(term)
  for kw in CASE_KEYWORDS.get(case_id, ()):
    if kw.lower() in blob:
      if kw not in hits:
        hits.append(kw)
  return hits[:8]


def _resolve_support_type(source: V8SourceRecord, evidence_needed: str) -> str:
  role = source.evidence_role.lower()
  stype = source.source_type.lower()
  if stype == "paper" or role in {"paper_evidence", "interface_evidence", "safety_evidence"}:
    return "paper_support_candidate"
  if stype == "web" or role == "web_signal":
    return "web_signal_candidate"
  if stype == "company" or role in {"company_signal", "market_signal"}:
    return "company_signal_candidate"
  if stype == "patent":
    if role == "example_source":
      return "direct_example_candidate"
    if role in {"claim_source", "claim_support", "process_claim_support"}:
      return "process_condition_candidate"
    if role in {"process_property", "interface_claim", "safety_claim"}:
      return "property_data_candidate"
  mapped = EVIDENCE_NEEDED_TO_SUPPORT.get(evidence_needed, "")
  if mapped and mapped != "claim_text_required":
    return mapped
  return "unknown"


def _resolve_support_level(
  *,
  claim: V8ClaimRecord,
  source: V8SourceRecord | None,
  support_type: str,
  matched: list[str],
) -> str:
  if claim.claim_text_status == "not_loaded" or support_type == "claim_text_required":
    return "needs_human_review" if source else "missing"
  if source is None:
    return "missing"
  stype = source.source_type.lower()
  if stype in {"web", "company"}:
    return "weak_candidate"
  if not source.url.strip():
    return "needs_human_review"
  if not matched:
    return "weak_candidate" if stype != "paper" else "not_assessed"
  if stype == "paper":
    return "medium_candidate"
  if stype == "patent" and source.evidence_role == "example_source":
    return "needs_human_review"
  if stype == "patent" and source.evidence_role in {"claim_source", "claim_support", "process_claim_support"}:
    return "medium_candidate"
  return "weak_candidate"


def _base_caution(source: V8SourceRecord | None) -> list[str]:
  flags = [
    "supporting_evidence_candidate",
    "evidence_map_not_proof",
    "no_legal_judgement",
    "heuristic_draft_link",
  ]
  if source and source.candidate_information_only:
    flags.append("candidate_information_only")
  if source and (source.human_review_required or not (source.url or "").strip()):
    flags.append("human_review_required")
  return flags


def _build_claim_text_required_link(claim: V8ClaimRecord, *, case_id: str) -> V8EvidenceLink:
  return V8EvidenceLink(
    evidence_link_id=_link_id(case_id, claim.claim_id, "", "claim_text_required"),
    case_id=case_id,
    publication_number=claim.publication_number,
    patent_title=claim.patent_title,
    claim_id=claim.claim_id,
    claim_no=claim.claim_no,
    claim_text_status=claim.claim_text_status,
    primary_axis=claim.primary_axis,
    technical_axis_labels=list(claim.technical_axis_labels),
    evidence_needed=list(claim.evidence_needed),
    support_type="claim_text_required",
    support_level="missing",
    match_reason="claim text is not loaded — Evidence link not assessed",
    matched_terms=[],
    evidence_gap="claim text is not loaded",
    next_verification_action="claims_input.csv または手動入力で claim 本文を追加する",
    verification_status="needs_human_review",
    human_review_required=True,
    caution_flags=[
      "claim_text_required",
      "supporting_evidence_candidate",
      "evidence_map_not_proof",
      "no_legal_judgement",
    ],
  )


def _build_missing_evidence_link(
  claim: V8ClaimRecord,
  *,
  case_id: str,
  needed: str,
) -> V8EvidenceLink:
  support_type = EVIDENCE_NEEDED_TO_SUPPORT.get(needed, "missing_evidence")
  return V8EvidenceLink(
    evidence_link_id=_link_id(case_id, claim.claim_id, f"missing:{needed}", support_type),
    case_id=case_id,
    publication_number=claim.publication_number,
    patent_title=claim.patent_title,
    claim_id=claim.claim_id,
    claim_no=claim.claim_no,
    claim_text_status=claim.claim_text_status,
    primary_axis=claim.primary_axis,
    technical_axis_labels=list(claim.technical_axis_labels),
    evidence_needed=[needed],
    support_type=support_type,
    support_level="missing",
    match_reason=f"no supporting source matched for evidence_needed={needed}",
    matched_terms=[],
    evidence_gap=f"missing evidence: {needed}",
    next_verification_action=f"人手で {needed} に該当する一次 source を確認・追加する",
    verification_status="needs_human_review",
    human_review_required=True,
    caution_flags=["missing_evidence", "evidence_map_not_proof", "no_legal_judgement"],
  )


def _build_source_link(
  claim: V8ClaimRecord,
  source: V8SourceRecord,
  *,
  case_id: str,
) -> V8EvidenceLink:
  matched = _matched_terms(claim, source, case_id)
  primary_needed = claim.evidence_needed[0] if claim.evidence_needed else "unknown"
  support_type = _resolve_support_type(source, primary_needed)
  support_level = _resolve_support_level(
    claim=claim, source=source, support_type=support_type, matched=matched,
  )
  pub_or_doi = source.publication_number or source.doi or ""
  reason_parts = [
    "heuristic draft — supporting evidence candidate only",
    f"source_type={source.source_type}",
    f"evidence_role={source.evidence_role}",
  ]
  if matched:
    reason_parts.append(f"matched_terms={', '.join(matched[:4])}")
  else:
    reason_parts.append("matched_terms=none (weak association)")

  gap = ""
  if support_type == "direct_example_candidate":
    gap = "example text not loaded — direct example support unverified"
  elif source.source_type == "paper":
    gap = "paper full text not read — claim correspondence unverified"
  elif source.source_type in {"web", "company"}:
    gap = "web/company signal — candidate information only"

  return V8EvidenceLink(
    evidence_link_id=_link_id(case_id, claim.claim_id, source.source_id, support_type),
    case_id=case_id,
    publication_number=claim.publication_number,
    patent_title=claim.patent_title,
    claim_id=claim.claim_id,
    claim_no=claim.claim_no,
    claim_text_status=claim.claim_text_status,
    primary_axis=claim.primary_axis,
    technical_axis_labels=list(claim.technical_axis_labels),
    evidence_needed=list(claim.evidence_needed),
    source_id=source.source_id,
    source_type=source.source_type,
    source_title=source.title,
    source_organization=source.organization,
    source_year=source.year,
    source_url=source.url,
    publication_number_or_doi=pub_or_doi,
    evidence_role=source.evidence_role,
    support_type=support_type,
    support_level=support_level,
    match_reason="; ".join(reason_parts),
    matched_terms=matched,
    evidence_gap=gap or "correspondence not verified — human review required",
    next_verification_action=(
      f"一次情報を確認: {source.title[:60]} "
      f"({source.url or 'URLなし'}) — claim {claim.claim_no} との対応は未確定"
    ),
    verification_status="source_url_available" if source.url.strip() else "needs_human_review",
    candidate_information_only=source.candidate_information_only,
    human_review_required=True,
    caution_flags=_base_caution(source),
    source_artifact_paths=[source.artifact_path] if source.artifact_path else [],
  )


def _count_field(links: list[V8EvidenceLink], attr: str) -> dict[str, int]:
  counts: dict[str, int] = {}
  for link in links:
    val = getattr(link, attr, "unknown") or "unknown"
    counts[val] = counts.get(val, 0) + 1
  return counts


def build_evidence_map(
  *,
  case_id: str,
  publication_number: str | None = None,
  project_root: Any = None,
  claim_map: V8ClaimMap | None = None,
  sources: V8SourcesTable | None = None,
  include_unloaded_claim_gaps: bool = True,
) -> V8EvidenceMap:
  root = project_root or project_root_from_here()
  warnings: list[str] = [EVIDENCE_MAP_SAFETY_NOTICES[0], EVIDENCE_MAP_SAFETY_NOTICES[1]]
  artifact_paths: list[str] = []

  claim_map_dir = find_latest_claim_map_dir(case_id, root)
  if claim_map_dir:
    artifact_paths.append(str(claim_map_dir))

  if claim_map is None:
    claim_map = build_claim_map(case_id=case_id, publication_number=publication_number, project_root=root)

  if sources is None:
    sources = load_sources_table(case_id, project_root=root)

  pub_filter = (publication_number or "").strip()
  claims = claim_map.records
  if pub_filter:
    claims = [c for c in claims if c.publication_number == pub_filter]

  case_sources = [s for s in sources.records if s.case_id == case_id or not s.case_id]
  non_patent_sources = [s for s in case_sources if s.source_type in {"paper", "web", "company"}]
  patent_sources = [s for s in case_sources if s.source_type == "patent"]

  links: list[V8EvidenceLink] = []
  claim_text_required_count = 0
  missing_evidence_count = 0

  for claim in claims:
    if claim.claim_text_status == "not_loaded":
      claim_text_required_count += 1
      links.append(_build_claim_text_required_link(claim, case_id=case_id))
      if include_unloaded_claim_gaps:
        for needed in claim.evidence_needed:
          if needed != "claim_text_loading_required":
            links.append(_build_missing_evidence_link(claim, case_id=case_id, needed=needed))
            missing_evidence_count += 1
      continue

    linked_needs: set[str] = set()
    relevant_sources = non_patent_sources + [
      p for p in patent_sources
      if p.publication_number != claim.publication_number or p.evidence_role == "example_source"
    ]
    for source in relevant_sources:
      matched = _matched_terms(claim, source, case_id)
      if not matched and source.source_type not in {"paper", "web", "company"}:
        continue
      link = _build_source_link(claim, source, case_id=case_id)
      links.append(link)
      for need in claim.evidence_needed:
        st = EVIDENCE_NEEDED_TO_SUPPORT.get(need, "")
        if st and link.support_type == st:
          linked_needs.add(need)

    for needed in claim.evidence_needed:
      if needed in linked_needs or needed == "claim_text_loading_required":
        continue
      links.append(_build_missing_evidence_link(claim, case_id=case_id, needed=needed))
      missing_evidence_count += 1

  primary_pub = pub_filter or claim_map.publication_number or "all"
  next_actions = [
    "claim text required の claim は本文投入後に Evidence Map を再生成",
    "paper / web / company は supporting evidence candidate として人手確認",
    "Evidence Gap 変化を次回メール Digest / Watch Profile 更新で追跡",
  ]

  return V8EvidenceMap(
    evidence_map_id=_map_id(case_id, primary_pub),
    case_id=case_id,
    publication_number=primary_pub,
    generated_at=utc_now_iso(),
    links=links,
    link_count=len(links),
    claim_count=len(claims),
    source_count=len(case_sources),
    count_by_support_type=_count_field(links, "support_type"),
    count_by_support_level=_count_field(links, "support_level"),
    count_by_source_type=_count_field(links, "source_type"),
    missing_evidence_count=missing_evidence_count,
    claim_text_required_count=claim_text_required_count,
    warnings=warnings,
    source_artifact_paths=artifact_paths,
    next_actions=next_actions,
  )
