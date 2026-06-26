"""v8 Claim Map builder — rule-based classification (Phase 27E)."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from tech_cartography.runtime.v8_claim_map_schema import (
  CLAIM_MAP_SAFETY_NOTICES,
  V8ClaimMap,
  V8ClaimRecord,
)
from tech_cartography.runtime.v8_patent_shortlist_schema import V8PatentShortlist
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_claim_input_loader import V8ClaimInputRow, load_claim_inputs
from tech_cartography.services.v8_patent_shortlist import build_patent_shortlist
from tech_cartography.services.v8_sources_table import load_case_profile, project_root_from_here

TECHNICAL_AXES: tuple[str, ...] = (
  "precursor",
  "stabilization",
  "carbonization",
  "graphitization",
  "sizing / surface treatment",
  "matrix / resin",
  "mechanical property",
  "microstructure",
  "pressure vessel / filament winding",
  "application",
  "unknown",
)

AXIS_KEYWORDS: dict[str, tuple[str, ...]] = {
  "precursor": ("pan", "polyacrylonitrile", "precursor", "precursor fiber", "stabilized fiber"),
  "stabilization": ("stabilization", "stabilized", "oxidation", "stabilize", "oxidize"),
  "carbonization": ("carbonization", "carbonize", "carbonizing", "carbonized", "pyrolysis"),
  "graphitization": ("graphitization", "graphitize", "graphite", "graphitized"),
  "sizing / surface treatment": (
    "sizing", "surface treatment", "surface-treated", "coating", "interface", "interfacial", "adhesion",
  ),
  "matrix / resin": ("matrix", "resin", "epoxy", "composite", "polymer matrix"),
  "mechanical property": (
    "tensile", "strength", "modulus", "elongation", "ilss", "shear strength", "mechanical property",
  ),
  "microstructure": ("microstructure", "crystallite", "crystal", "orientation", "structure"),
  "pressure vessel / filament winding": (
    "pressure vessel", "filament winding", "hydrogen tank", "liner", "hoop", "winding", "cfrp", "type iv",
  ),
  "application": ("application", "aircraft", "automotive", "hydrogen storage", "gas storage", "tank"),
}

CASE_BOOST_AXES: dict[str, tuple[str, ...]] = {
  "case_01_pan_graphitization": ("precursor", "stabilization", "carbonization", "graphitization", "mechanical property"),
  "case_02_sizing_interface": ("sizing / surface treatment", "matrix / resin", "mechanical property", "microstructure"),
  "case_03_pressure_vessel_filament_winding": (
    "pressure vessel / filament winding", "matrix / resin", "mechanical property", "application",
  ),
}

MATERIAL_PATTERNS: tuple[tuple[str, str], ...] = (
  (r"\bpan\b", "PAN"),
  (r"polyacrylonitrile", "polyacrylonitrile"),
  (r"precursor", "precursor"),
  (r"carbon fiber", "carbon fiber"),
  (r"epoxy", "epoxy"),
  (r"resin", "resin"),
  (r"matrix", "matrix"),
  (r"cfrp", "CFRP"),
  (r"liner", "liner"),
  (r"towpreg", "towpreg"),
)

PROCESS_PATTERNS: tuple[tuple[str, str], ...] = (
  (r"carboniz", "carbonization"),
  (r"graphitiz", "graphitization"),
  (r"stabiliz", "stabilization"),
  (r"oxidiz", "oxidation"),
  (r"sizing", "sizing"),
  (r"surface treat", "surface treatment"),
  (r"filament wind", "filament winding"),
  (r"winding", "winding"),
  (r"coating", "coating"),
)

PROPERTY_PATTERNS: tuple[tuple[str, str], ...] = (
  (r"tensile strength", "tensile strength"),
  (r"modulus", "modulus"),
  (r"elongation", "elongation"),
  (r"ilss", "ILSS"),
  (r"shear strength", "shear strength"),
  (r"burst", "burst"),
  (r"fatigue", "fatigue"),
)

STRUCTURE_PATTERNS: tuple[tuple[str, str], ...] = (
  (r"fiber bundle", "fiber bundle"),
  (r"layer", "layer"),
  (r"hoop", "hoop"),
  (r"microstructure", "microstructure"),
  (r"crystall", "crystalline structure"),
)

APPLICATION_PATTERNS: tuple[tuple[str, str], ...] = (
  (r"pressure vessel", "pressure vessel"),
  (r"hydrogen tank", "hydrogen tank"),
  (r"gas storage", "gas storage"),
  (r"composite", "composite application"),
)

CONDITION_PATTERNS: tuple[tuple[str, str], ...] = (
  (r"temperature", "temperature"),
  (r"\d+\s*°c", "temperature condition"),
  (r"atmosphere", "atmosphere"),
  (r"pressure", "pressure condition"),
)


def _claim_id(case_id: str, publication_number: str, claim_no: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{publication_number}|{claim_no}".encode()).hexdigest()[:12]
  return f"{case_id}:claim:{digest}"


def _claim_map_id(case_id: str, publication_number: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{publication_number}|claim_map".encode()).hexdigest()[:12]
  return f"{case_id}:claim_map:{digest}"


def _extract_terms(text: str, patterns: tuple[tuple[str, str], ...]) -> list[str]:
  lowered = text.lower()
  found: list[str] = []
  for pattern, label in patterns:
    if re.search(pattern, lowered, re.IGNORECASE):
      if label not in found:
        found.append(label)
  return found


def _classify_axes(text: str, case_id: str) -> list[str]:
  lowered = text.lower()
  hits: list[str] = []
  for axis, keywords in AXIS_KEYWORDS.items():
    if axis == "unknown":
      continue
    if any(kw in lowered for kw in keywords):
      hits.append(axis)
  boost = CASE_BOOST_AXES.get(case_id, ())
  ordered = [a for a in boost if a in hits] + [a for a in hits if a not in boost]
  return ordered or ["unknown"]


def _infer_evidence_needed(
  *,
  loaded: bool,
  process_terms: list[str],
  property_terms: list[str],
  structure_terms: list[str],
  application_terms: list[str],
) -> list[str]:
  if not loaded:
    return ["claim_text_loading_required"]
  needed: list[str] = []
  if process_terms:
    needed.append("process_condition_support")
  if property_terms:
    needed.append("property_data_support")
  if structure_terms:
    needed.append("structure_characterization_support")
  if application_terms:
    needed.append("application_validation_support")
  needed.append("example_support")
  needed.append("paper_support")
  return needed


def _evidence_priority(loaded: bool, evidence_needed: list[str]) -> str:
  if not loaded or "claim_text_loading_required" in evidence_needed:
    return "high"
  if len(evidence_needed) >= 4:
    return "high"
  if len(evidence_needed) >= 2:
    return "medium"
  return "low"


def _map_source_status(row: V8ClaimInputRow) -> tuple[str, str]:
  if not row.has_loaded_text():
    return "claim text not loaded", "not_loaded"
  source = row.claim_source_type.lower()
  if source in {
    "manual",
    "google_patents_user_copy",
    "bigquery_user_copy",
    "other_user_provided",
  }:
    return row.claim_text, "manual_input"
  if source == "csv":
    return row.claim_text, "csv_imported"
  if source in {"artifact", "uploaded_pdf"}:
    return row.claim_text, "artifact_imported"
  return row.claim_text, "loaded"


def build_claim_record(
  row: V8ClaimInputRow,
  *,
  case_id: str,
  patent_title_fallback: str = "",
) -> V8ClaimRecord:
  claim_text, claim_text_status = _map_source_status(row)
  loaded = claim_text_status != "not_loaded"
  title = row.patent_title or patent_title_fallback

  caution = [
    "heuristic_draft_classification",
    "technical_organization_not_legal_interpretation",
    "no_legal_judgement",
  ]
  if not loaded:
    caution.append("claim_text_not_loaded")
    return V8ClaimRecord(
      claim_id=_claim_id(case_id, row.publication_number, row.claim_no),
      case_id=case_id,
      publication_number=row.publication_number,
      patent_title=title,
      claim_no=row.claim_no,
      claim_text="claim text not loaded",
      claim_text_status="not_loaded",
      claim_source_type=row.claim_source_type or "unavailable",
      claim_source_path=row.claim_source_path,
      claim_source_url=row.claim_source_url,
      technical_axis_labels=["unknown"],
      primary_axis="unknown",
      evidence_needed=["claim_text_loading_required"],
      evidence_priority="high",
      why_this_claim_matters=(
        f"Patent Shortlist 候補 {row.publication_number} — claim text not loaded。"
        " 原典公報で請求項を取得後に再分類してください。"
      ),
      next_evidence_check=(
        f"請求項本文を claims_input.csv または手動入力で投入: {row.publication_number} claim {row.claim_no}"
      ),
      next_phase="Evidence Map",
      caution_flags=caution,
      human_review_required=True,
    )

  axes = _classify_axes(claim_text, case_id)
  material = _extract_terms(claim_text, MATERIAL_PATTERNS)
  process = _extract_terms(claim_text, PROCESS_PATTERNS)
  prop = _extract_terms(claim_text, PROPERTY_PATTERNS)
  structure = _extract_terms(claim_text, STRUCTURE_PATTERNS)
  application = _extract_terms(claim_text, APPLICATION_PATTERNS)
  condition = _extract_terms(claim_text, CONDITION_PATTERNS)
  evidence_needed = _infer_evidence_needed(
    loaded=True,
    process_terms=process,
    property_terms=prop,
    structure_terms=structure,
    application_terms=application,
  )

  return V8ClaimRecord(
    claim_id=_claim_id(case_id, row.publication_number, row.claim_no),
    case_id=case_id,
    publication_number=row.publication_number,
    patent_title=title,
    claim_no=row.claim_no,
    claim_text=claim_text,
    claim_text_status=claim_text_status,
    claim_source_type=row.claim_source_type,
    claim_source_path=row.claim_source_path,
    claim_source_url=row.claim_source_url,
    technical_axis_labels=axes,
    primary_axis=axes[0],
    material_terms=material,
    process_terms=process,
    property_terms=prop,
    structure_terms=structure,
    application_terms=application,
    condition_terms=condition,
    evidence_needed=evidence_needed,
    evidence_priority=_evidence_priority(True, evidence_needed),
    why_this_claim_matters=(
      f"heuristic draft — primary_axis={axes[0]}; "
      f"process={', '.join(process[:3]) or '—'}; property={', '.join(prop[:3]) or '—'}."
    ),
    next_evidence_check=(
      f"Evidence Map で {', '.join(evidence_needed[:3])} を照合: "
      f"{row.publication_number} claim {row.claim_no}"
    ),
    next_phase="Evidence Map",
    caution_flags=caution,
    human_review_required=True,
  )


def _count_by_axis(records: list[V8ClaimRecord]) -> dict[str, int]:
  counts: dict[str, int] = {}
  for rec in records:
    axis = rec.primary_axis or "unknown"
    counts[axis] = counts.get(axis, 0) + 1
  return counts


def _count_by_evidence(records: list[V8ClaimRecord]) -> dict[str, int]:
  counts: dict[str, int] = {}
  for rec in records:
    for item in rec.evidence_needed:
      counts[item] = counts.get(item, 0) + 1
  return counts


def build_claim_map(
  *,
  case_id: str,
  publication_number: str | None = None,
  project_root: Any = None,
  shortlist: V8PatentShortlist | None = None,
  claim_inputs: list[V8ClaimInputRow] | None = None,
  manual_rows: list[dict[str, Any]] | None = None,
  use_shortlist_only: bool = False,
) -> V8ClaimMap:
  root = project_root or project_root_from_here()
  if shortlist is None:
    shortlist = build_patent_shortlist(case_id=case_id, top_n=5, project_root=root)

  profile = load_case_profile(case_id, root) or {}
  del profile  # reserved for future axis tuning

  warnings: list[str] = [CLAIM_MAP_SAFETY_NOTICES[0]]
  artifact_paths: list[str] = []

  if use_shortlist_only:
    claim_inputs = []
    warnings.append("claim text未取得モード — claims_input.csv をスキップし not_loaded のみ生成")
  elif claim_inputs is None:
    claim_inputs, input_warnings, artifact_paths = load_claim_inputs(
      case_id,
      project_root=root,
      manual_rows=manual_rows,
    )
    warnings.extend(input_warnings)
  elif manual_rows:
    from tech_cartography.services.v8_claim_input_loader import merge_manual_claim_inputs

    extra = merge_manual_claim_inputs(manual_rows, case_id=case_id)
    by_key = {(r.publication_number, r.claim_no): r for r in claim_inputs}
    for row in extra:
      key = (row.publication_number, row.claim_no)
      if row.has_loaded_text() or key not in by_key:
        by_key[key] = row
    claim_inputs = list(by_key.values())

  pub_filter = (publication_number or "").strip()
  target_patents = shortlist.patent_candidates
  if pub_filter:
    target_patents = [p for p in target_patents if p.publication_number == pub_filter]
    if not target_patents:
      warnings.append(f"publication_number {pub_filter} not in Patent Shortlist")

  inputs_by_pub: dict[str, list[V8ClaimInputRow]] = {}
  for row in claim_inputs:
    if row.case_id and row.case_id != case_id:
      continue
    inputs_by_pub.setdefault(row.publication_number, []).append(row)

  records: list[V8ClaimRecord] = []
  primary_pub = pub_filter or (target_patents[0].publication_number if target_patents else "")

  if use_shortlist_only and not claim_inputs:
    warnings.append("building claim map without claims_input — all records not_loaded")

  for patent in target_patents:
    pub = patent.publication_number
    rows = inputs_by_pub.get(pub, [])
    if not rows:
      rows = [
        V8ClaimInputRow(
          case_id=case_id,
          publication_number=pub,
          patent_title=patent.title,
          claim_no="1",
          claim_text="",
          claim_source_type="unavailable",
          claim_source_url=patent.url,
          notes="auto placeholder — claim text loading required",
        ),
      ]
      warnings.append(f"no claims_input for {pub} — not_loaded record created")

    for row in rows:
      if not row.patent_title:
        row.patent_title = patent.title
      records.append(build_claim_record(row, case_id=case_id, patent_title_fallback=patent.title))

  loaded_count = sum(1 for r in records if r.claim_text_status != "not_loaded")
  not_loaded_count = len(records) - loaded_count

  next_actions = [
    "claim text not loaded の請求項は原典公報から本文を投入",
    "Evidence Map で example_support / paper_support を照合",
    "定点観測 Digest で Claim Map 軸の変化を追跡",
  ]

  return V8ClaimMap(
    claim_map_id=_claim_map_id(case_id, primary_pub or "all"),
    case_id=case_id,
    publication_number=primary_pub or "all",
    generated_at=utc_now_iso(),
    records=records,
    claim_count=len(records),
    loaded_claim_count=loaded_count,
    not_loaded_claim_count=not_loaded_count,
    count_by_axis=_count_by_axis(records),
    count_by_evidence_needed=_count_by_evidence(records),
    warnings=warnings,
    source_artifact_paths=artifact_paths,
    next_actions=next_actions,
  )
