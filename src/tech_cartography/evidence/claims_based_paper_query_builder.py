"""Build OpenAlex paper query candidates from manual claims and claim elements."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from tech_cartography.domain.claim_element import ClaimElement
from tech_cartography.evidence.paper_query_quality import (
  evaluate_paper_query_candidates,
  save_paper_query_quality_artifacts,
)

CLAIMS_ONLY_CAVEAT = (
  "この論文クエリは請求項ベースの限定的な裏取り候補です。"
  "明細書・実施例が未入力の場合、技術的妥当性の確認には限界があります。"
)
NUMERICAL_NO_DESC_CAVEAT = (
  "数値条件・実施例の裏取りは明細書未入力のため限定的です。"
  "論文は証明ではなく supporting evidence candidate として扱ってください。"
)
METADATA_ONLY_CAVEAT = (
  "請求項がないため、タイトル・要約ベースの低信頼度クエリです。"
)
PHASE18D_CAVEAT = (
  "この段階では、請求項とメタデータから生成した論文検索候補です。"
  "明細書・実施例が未入力のため、数値条件や測定方法の裏取りは限定的です。"
)

PRIORITY_TERMS = [
  "pan",
  "polyacrylonitrile",
  "carbon fiber",
  "precursor",
  "oxidation",
  "carbonization",
  "tensile strength",
  "modulus",
  "surface treatment",
  "sizing",
  "stabilization",
  "graphitization",
  "elastic modulus",
  "manufacturing",
  "mechanical properties",
  "microstructure",
  "interfacial adhesion",
]

DOMAIN_FALLBACK_TERMS = {
  "material": ["PAN", "polyacrylonitrile", "carbon fiber", "precursor fiber"],
  "process": ["oxidation", "stabilization", "carbonization", "manufacturing"],
  "property": ["tensile strength", "modulus", "mechanical properties", "elastic modulus"],
  "structure": ["fiber bundle", "precursor", "surface", "microstructure"],
  "application": ["composite", "pressure vessel", "aerospace"],
}

EXPANSION_TEMPLATES: list[tuple[str, str, str]] = [
  ("material_process", "polyacrylonitrile carbon fiber manufacturing carbonization", "expansion_core_material_process"),
  ("material_process", "PAN precursor oxidation carbonization carbon fiber", "expansion_pan_precursor_process"),
  ("property_condition", "carbon fiber tensile strength elastic modulus manufacturing process", "expansion_property_oriented"),
  ("property_condition", "PAN based carbon fiber mechanical properties carbonization", "expansion_pan_mechanical_properties"),
  ("surface_interface", "carbon fiber surface treatment sizing interfacial adhesion", "expansion_surface_interface"),
  ("surface_interface", "PAN carbon fiber surface modification composite interface", "expansion_surface_modification"),
  ("structure_property", "carbon fiber microstructure tensile strength modulus defects", "expansion_structure_property"),
  ("structure_property", "turbostratic carbon fiber structure mechanical properties", "expansion_turbostratic_structure"),
  ("process_condition", "carbon fiber oxidation carbonization temperature residence time", "expansion_process_condition"),
  ("process_condition", "PAN precursor stabilization carbonization process parameters", "expansion_stabilization_process"),
  ("application", "carbon fiber pressure vessel composite material tensile modulus", "expansion_pressure_vessel"),
  ("application", "carbon fiber reinforced composite pressure container", "expansion_composite_container"),
  ("measurement_method", "carbon fiber tensile strength modulus measurement method", "expansion_measurement_method"),
  ("measurement_method", "carbon fiber mechanical property evaluation PAN based", "expansion_mechanical_evaluation"),
  ("broad_background", "PAN based carbon fiber manufacturing review", "expansion_broad_review"),
  ("broad_background", "polyacrylonitrile carbon fiber stabilization carbonization review", "expansion_broad_stabilization_review"),
]

NUMERICAL_PATTERN = re.compile(
  r"\b\d+(?:\.\d+)?\s*(?:%|gpa|mpa|cN/dtex|dtex|°c|degc|nm|μm|um)\b",
  re.IGNORECASE,
)

ELEMENT_COMBINATIONS: list[tuple[str, str, str]] = [
  ("material", "process", "material_process"),
  ("material", "property", "property_condition"),
  ("process", "numerical_condition", "property_condition"),
  ("structure", "property", "structure_property"),
  ("application", "property", "application"),
  ("evaluation_method", "property", "measurement_method"),
]

QUERY_TYPE_TO_EVIDENCE = {
  "material_process": "process_supporting_literature",
  "property_condition": "property_measurement_literature",
  "structure_property": "structure_property_literature",
  "surface_interface": "interface_supporting_literature",
  "process_condition": "process_parameter_literature",
  "application": "application_background_literature",
  "measurement_method": "evaluation_method_literature",
  "broad_background": "background_literature",
}

GENERIC_QUERY_TERMS = frozenset(
  {"carbon", "fiber", "pan", "review", "manufacturing", "process", "method", "based"},
)


def determine_source_scope(record: dict[str, Any]) -> str:
  claims = str(record.get("claims") or record.get("claims_text") or "").strip()
  description = str(record.get("description") or record.get("description_text") or "").strip()
  if claims and description:
    return "manual_claims_and_description"
  if claims:
    return "manual_claims_only"
  return "metadata_only"


def _has_description(record: dict[str, Any]) -> bool:
  return bool(str(record.get("description") or record.get("description_text") or "").strip())


def _record_context_text(record: dict[str, Any]) -> str:
  return " ".join(
    [
      str(record.get("title") or ""),
      str(record.get("abstract") or ""),
      str(record.get("claims") or record.get("claims_text") or ""),
      str(record.get("assignee") or ""),
    ],
  ).lower()


def _extract_priority_terms(text: str) -> list[str]:
  lowered = text.lower()
  found: list[str] = []
  for term in PRIORITY_TERMS:
    if term in lowered and term not in found:
      found.append(term)
  return found


def _extract_numerical_snippets(text: str) -> list[str]:
  return [match.group(0).strip() for match in NUMERICAL_PATTERN.finditer(text or "")]


def classify_query_specificity(candidate: dict[str, Any]) -> str:
  query = str(candidate.get("query") or "").lower()
  query_type = str(candidate.get("query_type") or "broad_background")
  words = [w for w in query.split() if w]
  if query_type == "broad_background" or len(words) <= 3:
    return "broad"
  specific_markers = ("pan", "polyacrylonitrile", "carbonization", "tensile", "modulus", "oxidation")
  if any(marker in query for marker in specific_markers) and len(words) >= 5:
    return "specific"
  if NUMERICAL_PATTERN.search(query):
    return "specific"
  return "moderate"


def score_query_quality(candidate: dict[str, Any]) -> float:
  query_type = str(candidate.get("query_type") or "broad_background")
  confidence = str(candidate.get("confidence") or "low")
  specificity = classify_query_specificity(candidate)
  type_scores = {
    "material_process": 0.9,
    "property_condition": 0.85,
    "structure_property": 0.8,
    "surface_interface": 0.75,
    "process_condition": 0.75,
    "measurement_method": 0.7,
    "application": 0.65,
    "broad_background": 0.4,
  }
  score = type_scores.get(query_type, 0.5)
  if confidence == "medium":
    score += 0.05
  if specificity == "specific":
    score += 0.1
  elif specificity == "broad":
    score -= 0.15
  word_count = len(str(candidate.get("query") or "").split())
  if word_count < 4:
    score -= 0.1
  elif word_count > 8:
    score += 0.05
  return round(max(0.0, min(1.0, score)), 3)


def deduplicate_queries(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
  deduped: list[dict[str, Any]] = []
  seen: set[str] = set()
  for row in sorted(candidates, key=score_query_quality, reverse=True):
    query = " ".join(str(row.get("query") or "").split()).strip()
    if not query:
      continue
    key = query.lower()
    if key in seen:
      continue
    if any(key in existing or existing in key for existing in seen if len(key) > 10):
      continue
    seen.add(key)
    enriched = dict(row)
    enriched["query"] = query
    enriched["specificity"] = classify_query_specificity(enriched)
    enriched["quality_score"] = score_query_quality(enriched)
    deduped.append(enriched)
  return deduped


def _confidence_for_query(
  *,
  source_scope: str,
  query_type: str,
  has_description: bool,
  has_numerical: bool,
) -> str:
  if source_scope in {"metadata_only", "manual_claims_with_metadata_fallback"}:
    return "low"
  if source_scope == "manual_claims_only":
    if query_type in {"property_condition", "measurement_method", "process_condition"} and (
      has_numerical or not has_description
    ):
      return "low"
    if query_type == "broad_background":
      return "low"
    return "medium"
  if query_type in {"property_condition", "measurement_method", "process_condition"} and has_numerical and not has_description:
    return "low"
  if query_type == "broad_background":
    return "low"
  return "medium"


def _caveat_for_query(
  *,
  source_scope: str,
  query_type: str,
  has_description: bool,
  has_numerical: bool,
) -> str:
  if source_scope == "metadata_only":
    return METADATA_ONLY_CAVEAT
  if source_scope == "manual_claims_with_metadata_fallback":
    return f"{CLAIMS_ONLY_CAVEAT} Claim Elementが少ないため、メタデータ補完クエリを含みます。"
  if source_scope == "manual_claims_only":
    if query_type in {"property_condition", "measurement_method", "process_condition"} and (has_numerical or not has_description):
      return f"{CLAIMS_ONLY_CAVEAT} {NUMERICAL_NO_DESC_CAVEAT}"
    return CLAIMS_ONLY_CAVEAT
  if not has_description and query_type in {"property_condition", "measurement_method", "process_condition"}:
    return NUMERICAL_NO_DESC_CAVEAT
  return CLAIMS_ONLY_CAVEAT


def _make_query_row(
  *,
  publication_number: str,
  query: str,
  query_type: str,
  basis: str,
  record: dict[str, Any],
  has_numerical: bool = False,
  source_scope_override: str | None = None,
) -> dict[str, Any]:
  source_scope = source_scope_override or determine_source_scope(record)
  has_description = _has_description(record)
  confidence = _confidence_for_query(
    source_scope=source_scope,
    query_type=query_type,
    has_description=has_description,
    has_numerical=has_numerical,
  )
  row = {
    "query_id": f"cpq-{uuid.uuid4().hex[:8]}",
    "publication_number": publication_number,
    "query": query.strip(),
    "query_type": query_type,
    "basis": basis,
    "confidence": confidence,
    "source_scope": source_scope,
    "caveat_japanese": _caveat_for_query(
      source_scope=source_scope,
      query_type=query_type,
      has_description=has_description,
      has_numerical=has_numerical,
    ),
    "expected_evidence_type": QUERY_TYPE_TO_EVIDENCE.get(query_type, "background_literature"),
    "openalex_mode": "plan_only",
    "evidence_role": "supporting_evidence_candidate",
  }
  row["specificity"] = classify_query_specificity(row)
  row["quality_score"] = score_query_quality(row)
  return row


def _terms_for_type(elements: list[ClaimElement], element_type: str, limit: int = 3) -> list[str]:
  terms: list[str] = []
  for element in elements:
    if element.element_type != element_type:
      continue
    for term in element.normalized_terms:
      cleaned = str(term).strip()
      if cleaned and cleaned.lower() not in {t.lower() for t in terms}:
        terms.append(cleaned)
    if len(terms) >= limit:
      break
  return terms[:limit]


def _build_metadata_fallback_queries(
  publication_number: str,
  record: dict[str, Any],
  *,
  source_scope: str = "metadata_only",
) -> list[dict[str, Any]]:
  context = _record_context_text(record)
  rows: list[dict[str, Any]] = []
  for query_type, query, basis in EXPANSION_TEMPLATES[:8]:
    rows.append(
      _make_query_row(
        publication_number=publication_number,
        query=query,
        query_type=query_type,
        basis=basis,
        record=record,
        source_scope_override=source_scope,
      ),
    )
  if not rows:
    terms = _extract_priority_terms(context) or ["carbon fiber"]
    rows.append(
      _make_query_row(
        publication_number=publication_number,
        query=" ".join(terms[:4]),
        query_type="broad_background",
        basis="metadata_only_fallback",
        record=record,
        source_scope_override=source_scope,
      ),
    )
  return rows


def _build_sparse_element_fallback_queries(
  publication_number: str,
  record: dict[str, Any],
) -> list[dict[str, Any]]:
  context = _record_context_text(record)
  rows: list[dict[str, Any]] = []
  for category, terms in DOMAIN_FALLBACK_TERMS.items():
    selected = [term for term in terms if term.lower() in context]
    if not selected:
      selected = terms[:2]
    if category == "material":
      query = f"{' '.join(selected[:2])} oxidation carbonization carbon fiber"
      qtype = "material_process"
    elif category == "process":
      query = f"PAN precursor {' '.join(selected[:2])} carbon fiber"
      qtype = "process_condition"
    elif category == "property":
      query = f"carbon fiber {' '.join(selected[:2])} manufacturing process"
      qtype = "property_condition"
    elif category == "structure":
      query = f"carbon fiber {' '.join(selected[:2])} tensile strength modulus"
      qtype = "structure_property"
    else:
      if not any(token in context for token in ("composite", "pressure", "aerospace", "vessel")):
        continue
      query = f"carbon fiber {' '.join(selected[:2])} composite application"
      qtype = "application"
    rows.append(
      _make_query_row(
        publication_number=publication_number,
        query=query,
        query_type=qtype,
        basis=f"metadata_fallback_{category}",
        record=record,
        source_scope_override="manual_claims_with_metadata_fallback",
      ),
    )
  return rows


def _build_combination_queries(
  publication_number: str,
  elements: list[ClaimElement],
  record: dict[str, Any],
) -> list[dict[str, Any]]:
  rows: list[dict[str, Any]] = []
  claims_text = str(record.get("claims") or record.get("claims_text") or "")
  numericals = _extract_numerical_snippets(claims_text)

  for left_type, right_type, query_type in ELEMENT_COMBINATIONS:
    left_terms = _terms_for_type(elements, left_type)
    right_terms = _terms_for_type(elements, right_type)
    if not left_terms and not right_terms:
      continue
    query_parts = left_terms + right_terms
    if not query_parts:
      continue
    query = " ".join(query_parts[:6])
    has_numerical = bool(numericals) and right_type == "numerical_condition"
    if has_numerical and numericals:
      query = f"{query} {numericals[0]}"
    rows.append(
      _make_query_row(
        publication_number=publication_number,
        query=query,
        query_type=query_type,
        basis=f"{left_type}+{right_type}",
        record=record,
        has_numerical=has_numerical,
      ),
    )
  return rows


def _build_claims_text_queries(publication_number: str, record: dict[str, Any]) -> list[dict[str, Any]]:
  claims = str(record.get("claims") or record.get("claims_text") or "").strip()
  if not claims:
    return []

  rows: list[dict[str, Any]] = []
  priority_terms = _extract_priority_terms(claims)
  numericals = _extract_numerical_snippets(claims)

  if len(priority_terms) >= 2:
    rows.append(
      _make_query_row(
        publication_number=publication_number,
        query=" ".join(priority_terms[:6]),
        query_type="material_process",
        basis="claims_priority_terms",
        record=record,
      ),
    )

  if any(term in claims.lower() for term in ("pan", "polyacrylonitrile", "precursor")):
    rows.append(
      _make_query_row(
        publication_number=publication_number,
        query="PAN precursor fiber oxidation carbonization surface treatment carbon fiber",
        query_type="material_process",
        basis="claims_domain_template",
        record=record,
      ),
    )

  if any(term in claims.lower() for term in ("tensile strength", "modulus", "elastic modulus", "mechanical")):
    query = "polyacrylonitrile carbon fiber carbonization tensile strength modulus"
    if numericals:
      query = f"{query} {numericals[0]}"
    rows.append(
      _make_query_row(
        publication_number=publication_number,
        query=query,
        query_type="property_condition",
        basis="claims_property_terms",
        record=record,
        has_numerical=bool(numericals),
      ),
    )

  if numericals:
    rows.append(
      _make_query_row(
        publication_number=publication_number,
        query=f"carbon fiber tensile strength modulus {numericals[0]} PAN carbonization",
        query_type="property_condition",
        basis="claims_numerical_condition",
        record=record,
        has_numerical=True,
      ),
    )

  if any(token in claims.lower() for token in ("surface", "sizing", "interface", "adhesion")):
    rows.append(
      _make_query_row(
        publication_number=publication_number,
        query="carbon fiber surface treatment sizing interfacial adhesion composite",
        query_type="surface_interface",
        basis="claims_surface_terms",
        record=record,
      ),
    )

  if "manufactur" in claims.lower() or "method" in claims.lower():
    rows.append(
      _make_query_row(
        publication_number=publication_number,
        query="carbon fiber method of manufacturing tensile strength elastic modulus",
        query_type="material_process",
        basis="claims_manufacturing_template",
        record=record,
      ),
    )

  return rows


def expand_claims_based_queries(
  record: dict[str, Any],
  claim_elements: list[ClaimElement | dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
  publication_number = str(record.get("publication_number") or "").strip()
  if not publication_number:
    return []

  elements: list[ClaimElement] = []
  for item in claim_elements or []:
    elements.append(item if isinstance(item, ClaimElement) else ClaimElement.from_dict(item))

  claims = str(record.get("claims") or record.get("claims_text") or "").strip()
  context = _record_context_text(record)

  if not claims and not elements:
    return _build_metadata_fallback_queries(publication_number, record)

  rows: list[dict[str, Any]] = []
  rows.extend(_build_combination_queries(publication_number, elements, record))
  rows.extend(_build_claims_text_queries(publication_number, record))

  for query_type, query, basis in EXPANSION_TEMPLATES:
    if any(token in context for token in query.lower().split()[:3]) or query_type != "application":
      rows.append(
        _make_query_row(
          publication_number=publication_number,
          query=query,
          query_type=query_type,
          basis=basis,
          record=record,
          has_numerical=bool(_extract_numerical_snippets(claims)),
        ),
      )

  if len(elements) < 3:
    rows.extend(_build_sparse_element_fallback_queries(publication_number, record))

  return deduplicate_queries(rows)


def ensure_minimum_query_candidates(
  candidates: list[dict[str, Any]],
  record: dict[str, Any],
  *,
  min_queries: int = 5,
  max_queries: int = 10,
) -> list[dict[str, Any]]:
  publication_number = str(record.get("publication_number") or "").strip()
  rows = list(candidates)
  existing_types = {str(row.get("query_type")) for row in rows}

  for query_type, query, basis in EXPANSION_TEMPLATES:
    if len(rows) >= min_queries:
      break
    if query_type in existing_types and sum(1 for r in rows if r.get("query_type") == query_type) >= 2:
      continue
    rows.append(
      _make_query_row(
        publication_number=publication_number,
        query=query,
        query_type=query_type,
        basis=f"min_fill_{basis}",
        record=record,
        source_scope_override=(
          "manual_claims_with_metadata_fallback"
          if not str(record.get("claims") or record.get("claims_text") or "").strip()
          else None
        ),
      ),
    )
    existing_types.add(query_type)

  ranked = sorted(deduplicate_queries(rows), key=score_query_quality, reverse=True)
  broad_rows = [r for r in ranked if r.get("query_type") == "broad_background"]
  if not broad_rows:
    for query_type, query, basis in EXPANSION_TEMPLATES:
      if query_type == "broad_background":
        broad_rows = [
          _make_query_row(
            publication_number=publication_number,
            query=query,
            query_type=query_type,
            basis=f"min_broad_{basis}",
            record=record,
          ),
        ]
        break
  non_broad = [r for r in ranked if r.get("query_type") != "broad_background"]
  reserved = max_queries - 1 if max_queries > 1 else max_queries
  merged = non_broad[:reserved] + broad_rows[:1]
  return deduplicate_queries(merged)[:max_queries]


def build_claims_paper_query_candidates(
  record: dict[str, Any],
  claim_elements: list[ClaimElement | dict[str, Any]] | None = None,
  *,
  min_queries: int = 5,
  max_queries: int = 10,
) -> list[dict[str, Any]]:
  expanded = expand_claims_based_queries(record, claim_elements)
  return ensure_minimum_query_candidates(
    expanded,
    record,
    min_queries=min_queries,
    max_queries=max_queries,
  )


def build_claims_paper_queries_for_records(
  records: list[dict[str, Any]],
  elements_by_publication: dict[str, list[ClaimElement | dict[str, Any]]] | None = None,
  *,
  min_queries: int = 5,
  max_queries: int = 10,
) -> list[dict[str, Any]]:
  elements_by_publication = elements_by_publication or {}
  all_rows: list[dict[str, Any]] = []
  for record in records:
    pub = str(record.get("publication_number") or "").strip()
    if not pub:
      continue
    per_record_max = max_queries
    rows = build_claims_paper_query_candidates(
      record,
      elements_by_publication.get(pub, []),
      min_queries=min_queries,
      max_queries=per_record_max,
    )
    all_rows.extend(rows)
  return deduplicate_queries(all_rows)[: max_queries * max(len(records), 1)]


def prioritize_claims_paper_queries(queries: list[dict[str, Any]], top_n: int = 12) -> list[dict[str, Any]]:
  return sorted(queries, key=score_query_quality, reverse=True)[:top_n]


def group_elements_by_publication(
  elements: list[ClaimElement | dict[str, Any]],
) -> dict[str, list[ClaimElement]]:
  grouped: dict[str, list[ClaimElement]] = {}
  for item in elements:
    element = item if isinstance(item, ClaimElement) else ClaimElement.from_dict(item)
    pub = str(element.publication_number or "").strip()
    if not pub:
      continue
    grouped.setdefault(pub, []).append(element)
  return grouped


def build_claims_paper_query_plan(
  records: list[dict[str, Any]],
  claim_element_result: dict[str, Any] | None = None,
  *,
  min_queries: int = 5,
  max_queries: int = 10,
) -> dict[str, Any]:
  elements = []
  if claim_element_result:
    for element in claim_element_result.get("elements", []):
      elements.append(element.to_dict() if hasattr(element, "to_dict") else element)
  grouped = group_elements_by_publication(elements)

  manual_records = [
    record
    for record in records
    if str(record.get("retrieval_status") or "") in {"manual_claims_loaded", "manual_fulltext_loaded"}
    or record.get("manual_route")
    or determine_source_scope(record) in {"manual_claims_only", "manual_claims_and_description"}
  ]
  target_records = manual_records or [r for r in records if str(r.get("claims") or r.get("claims_text") or "").strip()]
  if not target_records:
    target_records = [r for r in records if str(r.get("title") or r.get("abstract") or "").strip()]

  if len(target_records) == 1:
    record = target_records[0]
    pub = str(record.get("publication_number") or "")
    queries = build_claims_paper_query_candidates(
      record,
      grouped.get(pub, []),
      min_queries=min_queries,
      max_queries=max_queries,
    )
  else:
    queries = build_claims_paper_queries_for_records(
      target_records,
      grouped,
      min_queries=min_queries,
      max_queries=max_queries,
    )

  quality_summary = evaluate_paper_query_candidates(queries)
  type_distribution = quality_summary.get("query_type_distribution", {})
  examples = [row.get("query") for row in queries[:5]]
  confidences = sorted({str(row.get("confidence", "low")) for row in queries})

  return {
    "total_queries": len(queries),
    "queries": queries,
    "query_examples": examples,
    "confidence_levels": confidences,
    "query_type_distribution": type_distribution,
    "confidence_distribution": quality_summary.get("confidence_distribution", {}),
    "quality_summary": quality_summary,
    "plan_ready_for_openalex": quality_summary.get("plan_ready_for_openalex", False),
    "openalex_mode": "plan_only",
    "caveat_japanese": PHASE18D_CAVEAT,
    "target_publications": [str(r.get("publication_number")) for r in target_records],
    "next_actions_japanese": quality_summary.get("next_actions_japanese", []),
    "min_queries": min_queries,
    "max_queries": max_queries,
  }


def render_claims_paper_query_plan_markdown(plan: dict[str, Any]) -> str:
  quality = plan.get("quality_summary") or {}
  lines = [
    "# Claims-based Paper Query Plan",
    "",
    f"- total queries: {plan.get('total_queries', 0)}",
    f"- OpenAlex mode: {plan.get('openalex_mode', 'plan_only')}",
    f"- plan ready for OpenAlex: {plan.get('plan_ready_for_openalex', False)}",
    f"- confidence levels: {', '.join(plan.get('confidence_levels', [])) or 'n/a'}",
    "",
    "## query_type distribution",
    "",
  ]
  for qtype, count in sorted((plan.get("query_type_distribution") or {}).items()):
    lines.append(f"- {qtype}: {count}")

  lines.extend(["", "## Caveat", "", plan.get("caveat_japanese") or PHASE18D_CAVEAT, "", "## Query examples", ""])
  for example in plan.get("query_examples", []):
    lines.append(f"- {example}")
  if not plan.get("query_examples"):
    lines.append("- (no queries generated)")

  lines.extend(["", "## Next actions", ""])
  for action in plan.get("next_actions_japanese", []):
    lines.append(f"- {action}")
  lines.append("")
  lines.append("※ 論文は証明ではなく supporting evidence candidate です。金額情報は含みません。")
  if quality:
    lines.extend(
      [
        "",
        "## Quality summary",
        "",
        f"- duplicate count: {quality.get('duplicate_count', 0)}",
        f"- material/process covered: {quality.get('has_material_process_query', False)}",
        f"- property covered: {quality.get('has_property_query', False)}",
      ],
    )
  return "\n".join(lines)


def save_claims_paper_query_artifacts(
  plan: dict[str, Any],
  output_dir: str | Path,
  *,
  include_quality_report: bool = True,
) -> dict[str, str]:
  from tech_cartography.reports.project_export import save_records_csv

  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  queries = plan.get("queries", [])
  json_path = out / "paper_query_candidates_from_claims.json"
  csv_path = out / "paper_query_candidates_from_claims.csv"
  md_path = out / "claims_paper_query_plan.md"

  json_path.write_text(json.dumps(queries, indent=2, ensure_ascii=False), encoding="utf-8")
  save_records_csv(queries, csv_path)
  md_path.write_text(render_claims_paper_query_plan_markdown(plan), encoding="utf-8")

  paths = {
    "paper_query_candidates_from_claims_json": str(json_path),
    "paper_query_candidates_from_claims_csv": str(csv_path),
    "claims_paper_query_plan_md": str(md_path),
  }
  if include_quality_report:
    paths.update(
      save_paper_query_quality_artifacts(
        queries,
        out,
        summary=plan.get("quality_summary"),
      ),
    )
  return paths
