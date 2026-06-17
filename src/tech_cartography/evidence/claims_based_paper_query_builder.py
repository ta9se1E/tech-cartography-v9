"""Build OpenAlex paper query candidates from manual claims and claim elements."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from tech_cartography.domain.claim_element import ClaimElement

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
  "application": "application_background_literature",
  "measurement_method": "evaluation_method_literature",
  "broad_background": "background_literature",
}


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


def _extract_priority_terms(text: str) -> list[str]:
  lowered = text.lower()
  found: list[str] = []
  for term in PRIORITY_TERMS:
    if term in lowered and term not in found:
      found.append(term)
  return found


def _extract_numerical_snippets(text: str) -> list[str]:
  return [match.group(0).strip() for match in NUMERICAL_PATTERN.finditer(text or "")]


def _confidence_for_query(
  *,
  source_scope: str,
  query_type: str,
  has_description: bool,
  has_numerical: bool,
) -> str:
  if source_scope == "metadata_only":
    return "low"
  if source_scope == "manual_claims_only":
    if query_type in {"property_condition", "measurement_method"} and (has_numerical or not has_description):
      return "low"
    return "medium"
  if query_type in {"property_condition", "measurement_method"} and has_numerical and not has_description:
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
  if source_scope == "manual_claims_only":
    if query_type in {"property_condition", "measurement_method"} and has_numerical:
      return f"{CLAIMS_ONLY_CAVEAT} {NUMERICAL_NO_DESC_CAVEAT}"
    return CLAIMS_ONLY_CAVEAT
  if not has_description and query_type in {"property_condition", "measurement_method"}:
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
) -> dict[str, Any]:
  source_scope = determine_source_scope(record)
  has_description = _has_description(record)
  confidence = _confidence_for_query(
    source_scope=source_scope,
    query_type=query_type,
    has_description=has_description,
    has_numerical=has_numerical,
  )
  return {
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
    query = " ".join(priority_terms[:6])
    rows.append(
      _make_query_row(
        publication_number=publication_number,
        query=query,
        query_type="material_process",
        basis="claims_priority_terms",
        record=record,
      ),
    )

  if any(term in claims.lower() for term in ("pan", "polyacrylonitrile", "precursor")) and "carbonization" in claims.lower():
    rows.append(
      _make_query_row(
        publication_number=publication_number,
        query="PAN precursor fiber oxidation carbonization surface treatment carbon fiber",
        query_type="material_process",
        basis="claims_domain_template",
        record=record,
      ),
    )

  if any(term in claims.lower() for term in ("tensile strength", "modulus", "elastic modulus")):
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

  if len(priority_terms) <= 1:
    title = str(record.get("title") or "")
    abstract = str(record.get("abstract") or "")
    broad = " ".join(_extract_priority_terms(f"{title} {abstract} {claims}")[:4] or ["carbon fiber PAN precursor"])
    rows.append(
      _make_query_row(
        publication_number=publication_number,
        query=broad,
        query_type="broad_background",
        basis="claims_abstract_fallback",
        record=record,
      ),
    )

  return rows


def _build_metadata_fallback_queries(publication_number: str, record: dict[str, Any]) -> list[dict[str, Any]]:
  title = str(record.get("title") or "")
  abstract = str(record.get("abstract") or "")
  assignee = str(record.get("assignee") or "")
  text = f"{title} {abstract} {assignee}".strip()
  if not text:
    return []
  terms = _extract_priority_terms(text) or ["carbon fiber"]
  query = " ".join(terms[:4])
  row = _make_query_row(
    publication_number=publication_number,
    query=query,
    query_type="broad_background",
    basis="metadata_only_fallback",
    record=record,
  )
  row["confidence"] = "low"
  row["source_scope"] = "metadata_only"
  row["caveat_japanese"] = METADATA_ONLY_CAVEAT
  return [row]


def build_claims_paper_query_candidates(
  record: dict[str, Any],
  claim_elements: list[ClaimElement | dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
  publication_number = str(record.get("publication_number") or "").strip()
  claims = str(record.get("claims") or record.get("claims_text") or "").strip()
  if not publication_number:
    return []

  elements: list[ClaimElement] = []
  for item in claim_elements or []:
    elements.append(item if isinstance(item, ClaimElement) else ClaimElement.from_dict(item))

  if not claims and not elements:
    return _build_metadata_fallback_queries(publication_number, record)
  if not claims:
    return _build_metadata_fallback_queries(publication_number, record)

  rows: list[dict[str, Any]] = []
  rows.extend(_build_combination_queries(publication_number, elements, record))
  rows.extend(_build_claims_text_queries(publication_number, record))

  deduped: list[dict[str, Any]] = []
  seen: set[str] = set()
  for row in rows:
    key = row["query"].lower()
    if not key or key in seen:
      continue
    seen.add(key)
    deduped.append(row)
  return deduped


def build_claims_paper_queries_for_records(
  records: list[dict[str, Any]],
  elements_by_publication: dict[str, list[ClaimElement | dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
  elements_by_publication = elements_by_publication or {}
  all_rows: list[dict[str, Any]] = []
  for record in records:
    pub = str(record.get("publication_number") or "").strip()
    if not pub:
      continue
    rows = build_claims_paper_query_candidates(record, elements_by_publication.get(pub, []))
    all_rows.extend(rows)
  return prioritize_claims_paper_queries(all_rows)


def prioritize_claims_paper_queries(queries: list[dict[str, Any]], top_n: int = 30) -> list[dict[str, Any]]:
  confidence_order = {"medium": 0, "low": 1}
  type_order = {
    "material_process": 0,
    "property_condition": 1,
    "structure_property": 2,
    "measurement_method": 3,
    "application": 4,
    "broad_background": 5,
  }

  def sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
    return (
      confidence_order.get(str(row.get("confidence", "low")), 9),
      type_order.get(str(row.get("query_type", "broad_background")), 9),
      str(row.get("query", "")),
    )

  return sorted(queries, key=sort_key)[:top_n]


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
    target_records = [
      r for r in records
      if str(r.get("title") or r.get("abstract") or "").strip()
    ]

  queries = build_claims_paper_queries_for_records(target_records, grouped)
  examples = [row.get("query") for row in queries[:5]]
  confidences = sorted({str(row.get("confidence", "low")) for row in queries})

  return {
    "total_queries": len(queries),
    "queries": queries,
    "query_examples": examples,
    "confidence_levels": confidences,
    "openalex_mode": "plan_only",
    "caveat_japanese": CLAIMS_ONLY_CAVEAT,
    "target_publications": [str(r.get("publication_number")) for r in target_records],
    "next_actions_japanese": [
      "descriptionを追加する",
      "OpenAlexを限定実行する",
      "技術者がquery妥当性を確認する",
    ],
  }


def render_claims_paper_query_plan_markdown(plan: dict[str, Any]) -> str:
  lines = [
    "# Claims-based Paper Query Plan",
    "",
    f"- total queries: {plan.get('total_queries', 0)}",
    f"- OpenAlex mode: {plan.get('openalex_mode', 'plan_only')}",
    f"- confidence levels: {', '.join(plan.get('confidence_levels', [])) or 'n/a'}",
    "",
    "## Caveat",
    "",
    plan.get("caveat_japanese") or CLAIMS_ONLY_CAVEAT,
    "",
    "## Query examples",
    "",
  ]
  for example in plan.get("query_examples", []):
    lines.append(f"- {example}")
  if not plan.get("query_examples"):
    lines.append("- (no queries generated)")

  lines.extend(["", "## Next actions", ""])
  for action in plan.get("next_actions_japanese", []):
    lines.append(f"- {action}")
  lines.append("")
  lines.append("※ 論文は証明ではなく supporting evidence candidate です。金額情報は含みません。")
  return "\n".join(lines)


def save_claims_paper_query_artifacts(
  plan: dict[str, Any],
  output_dir: str | Path,
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

  return {
    "paper_query_candidates_from_claims_json": str(json_path),
    "paper_query_candidates_from_claims_csv": str(csv_path),
    "claims_paper_query_plan_md": str(md_path),
  }
