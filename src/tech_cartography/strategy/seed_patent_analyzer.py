"""Seed patent analysis for search strategy building."""

from __future__ import annotations

import re
from typing import Any

from tech_cartography.domain.patent_record import PatentRecord

MATERIAL_VOCABULARY = [
  "PAN",
  "polyacrylonitrile",
  "carbon fiber",
  "carbon fibre",
  "CFRP",
  "precursor fiber",
]

PROCESS_VOCABULARY = [
  "stabilization",
  "oxidation",
  "carbonization",
  "graphitization",
  "surface treatment",
  "sizing",
  "heat treatment",
]

PROPERTY_VOCABULARY = [
  "tensile strength",
  "modulus",
  "defect",
  "void",
  "density",
  "crystallite",
  "orientation",
  "interface adhesion",
]

APPLICATION_VOCABULARY = [
  "aerospace",
  "pressure vessel",
  "prepreg",
  "composite",
  "automotive",
  "spring",
]

DEFAULT_EXCLUDE_CANDIDATES = [
  "battery",
  "graphene",
  "carbon nanotube",
  "activated carbon",
  "carbon black",
]

PROTECTED_TERMS = {
  "pan",
  "polyacrylonitrile",
  "carbon fiber",
  "carbon fibre",
  "cfrp",
  "carbonization",
  "stabilization",
}

KNOWN_COMPANY_KEYWORDS = [
  "toray",
  "teijin",
  "mitsubishi chemical",
  "mitsubishi",
  "hyosung",
  "zhongfu shenying",
  "hexcel",
  "zoltek",
]

NUMERICAL_PATTERNS = [
  re.compile(r"\b\d{3,4}\s*(?:°|度|℃|C)\b", re.IGNORECASE),
  re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:MPa|GPa|cN/dtex|Pa)\b",
    re.IGNORECASE,
  ),
  re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:min|mins|minute|minutes|hr|hrs|hour|hours)\b",
    re.IGNORECASE,
  ),
  re.compile(r"\b\d+(?:\.\d+)?\s*%\b"),
]


def _dedupe_terms(terms: list[str]) -> list[str]:
  seen: set[str] = set()
  deduped: list[str] = []
  for term in terms:
    normalized = term.strip()
    if not normalized:
      continue
    key = normalized.lower()
    if key in seen:
      continue
    seen.add(key)
    deduped.append(normalized)
  return deduped


def _merge_terms(*groups: list[str]) -> list[str]:
  merged: list[str] = []
  for group in groups:
    merged.extend(group)
  return _dedupe_terms(merged)


def _term_in_text(text: str, term: str) -> bool:
  normalized = term.lower()
  if normalized == "pan":
    return bool(re.search(r"\bpan\b", text, re.IGNORECASE))
  return normalized in text


def _extract_terms_from_text(text: str, vocabulary: list[str]) -> list[str]:
  matches: list[str] = []
  for term in vocabulary:
    if _term_in_text(text, term):
      matches.append(term)
  return _dedupe_terms(matches)


def _extract_numerical_conditions(text: str) -> list[str]:
  matches: list[str] = []
  for pattern in NUMERICAL_PATTERNS:
    for match in pattern.finditer(text):
      snippet = re.sub(r"\s+", " ", match.group(0)).strip()
      if snippet and snippet.lower() not in {item.lower() for item in matches}:
        matches.append(snippet)
  return matches


def _is_broken_numeric_term(term: str) -> bool:
  compact = re.sub(r"\s+", "", term.lower())
  match = re.match(r"^(\d+(?:\.\d+)?)(gpa)$", compact)
  if not match:
    return False
  number_text = match.group(1)
  if re.fullmatch(r"0\d+", number_text):
    return True
  return "." not in number_text and len(number_text) <= 2


def _extract_companies(text: str, records: list[PatentRecord]) -> list[str]:
  found: list[str] = []
  for keyword in KNOWN_COMPANY_KEYWORDS:
    if keyword in text:
      found.append(keyword.title() if keyword.islower() else keyword)
  for record in records:
    if record.assignee:
      found.append(record.assignee)
  return _dedupe_terms(found)


def extract_seed_terms(seed_patents: list[PatentRecord]) -> dict[str, list[str]]:
  """Extract categorized terms from seed patents."""
  combined = " ".join(record.combined_text() for record in seed_patents)

  materials = _extract_terms_from_text(combined, MATERIAL_VOCABULARY)
  processes = _extract_terms_from_text(combined, PROCESS_VOCABULARY)
  properties = _extract_terms_from_text(combined, PROPERTY_VOCABULARY)
  applications = _extract_terms_from_text(combined, APPLICATION_VOCABULARY)
  companies = _extract_companies(combined, seed_patents)
  numerical_conditions = _extract_numerical_conditions(combined)

  candidate_include_terms = _merge_terms(
    materials,
    processes,
    properties,
    applications,
  )
  candidate_exclude_terms = _extract_terms_from_text(
    combined,
    DEFAULT_EXCLUDE_CANDIDATES,
  )

  warnings: list[str] = []
  if re.search(r"\bprecursor\b", combined, re.IGNORECASE) and not re.search(
    r"\bprecursor fiber\b",
    combined,
    re.IGNORECASE,
  ):
    warnings.append(
      "Standalone 'precursor' can be noisy; prefer 'precursor fiber' or PAN context.",
    )

  return {
    "materials": materials,
    "processes": processes,
    "properties": properties,
    "applications": applications,
    "companies": companies,
    "numerical_conditions": numerical_conditions,
    "candidate_include_terms": candidate_include_terms,
    "candidate_exclude_terms": candidate_exclude_terms,
    "warnings": warnings,
  }


def sanitize_seed_terms(
  terms: dict[str, Any],
  exclude_terms: list[str] | None = None,
) -> dict[str, Any]:
  """Sanitize extracted seed terms for search strategy use."""
  terms = terms or {}
  exclude_terms = exclude_terms or []

  sanitized_include = _merge_terms(
    list(terms.get("materials", [])),
    list(terms.get("processes", [])),
    list(terms.get("properties", [])),
    list(terms.get("applications", [])),
    list(terms.get("candidate_include_terms", [])),
  )

  sanitized_exclude = _merge_terms(
    list(terms.get("candidate_exclude_terms", [])),
    exclude_terms,
  )

  removed_terms: list[str] = []
  warnings: list[str] = list(terms.get("warnings", []))
  protected_removed = False

  final_exclude: list[str] = []
  for term in sanitized_exclude:
    key = term.lower()
    if key in PROTECTED_TERMS or key == "pan":
      removed_terms.append(term)
      protected_removed = True
      if key not in {item.lower() for item in sanitized_include}:
        sanitized_include.append(term)
      continue
    final_exclude.append(term)

  sanitized_numerical: list[str] = []
  for term in list(terms.get("numerical_conditions", [])):
    if _is_broken_numeric_term(term):
      removed_terms.append(term)
      warnings.append("Some broken numeric terms from PDF extraction were removed.")
      continue
    sanitized_numerical.append(term)

  include_text = " ".join(sanitized_include).lower()
  if (
    re.search(r"\bprecursor\b", include_text)
    and "precursor fiber" not in include_text
    and not any("precursor" in warning.lower() for warning in warnings)
  ):
    warnings.append(
      "Standalone 'precursor' can be noisy; prefer 'precursor fiber' or PAN context.",
    )

  if protected_removed:
    warnings.append(
      "Seed terms were sanitized. PAN was kept as a target material, not an exclude term.",
    )

  return {
    "materials": _dedupe_terms(list(terms.get("materials", []))),
    "processes": _dedupe_terms(list(terms.get("processes", []))),
    "properties": _dedupe_terms(list(terms.get("properties", []))),
    "applications": _dedupe_terms(list(terms.get("applications", []))),
    "companies": _dedupe_terms(list(terms.get("companies", []))),
    "numerical_conditions": sanitized_numerical,
    "candidate_include_terms": sanitized_include,
    "candidate_exclude_terms": final_exclude,
    "removed_terms": _dedupe_terms(removed_terms),
    "warnings": _dedupe_terms(warnings),
  }


def summarize_seed_evidence_coverage(seed_patents: list[PatentRecord]) -> dict[str, Any]:
  """Summarize how much evidence is available in seed patents."""
  if not seed_patents:
    return {
      "seed_count": 0,
      "has_claims": False,
      "has_examples": False,
      "has_measured_properties": False,
      "coverage_level": "Low",
      "publication_numbers": [],
    }

  has_claims = any(record.claims for record in seed_patents)
  has_examples = any(record.examples or record.description for record in seed_patents)
  has_measured_properties = any(record.measured_properties for record in seed_patents)

  score = sum([has_claims, has_examples, has_measured_properties])
  if score >= 2:
    coverage_level = "High"
  elif score == 1:
    coverage_level = "Medium"
  else:
    coverage_level = "Low"

  return {
    "seed_count": len(seed_patents),
    "has_claims": has_claims,
    "has_examples": has_examples,
    "has_measured_properties": has_measured_properties,
    "coverage_level": coverage_level,
    "publication_numbers": [
      record.publication_number
      for record in seed_patents
      if record.publication_number
    ],
  }


def analyze_seed_patents(seed_patents: list[PatentRecord]) -> dict[str, Any]:
  """Analyze seed patents and return search strategy hints."""
  extracted = extract_seed_terms(seed_patents)
  sanitized = sanitize_seed_terms(extracted)
  coverage = summarize_seed_evidence_coverage(seed_patents)

  warnings = list(sanitized.get("warnings", []))
  if coverage["seed_count"] == 0:
    warnings.append("seed patent records are empty")
  elif coverage["coverage_level"] == "Low":
    warnings.append("seed patent quality is low; upload richer seed patents if possible")

  return {
    **extracted,
    **sanitized,
    "seed_summary": coverage,
    "warnings": _dedupe_terms(warnings),
  }
