"""Rule-based claim element extraction."""

from __future__ import annotations

import re
import uuid
from typing import Any

from tech_cartography.domain.claim_element import ClaimElement

PHRASE_SPLIT_PATTERN = re.compile(
  r"(?:;|,|\bwherein\b|\bcomprising\b|\bincluding\b|\bcharacterized by\b|および| wherein )",
  flags=re.IGNORECASE,
)

VOCABULARY: dict[str, list[str]] = {
  "material": [
    "pan",
    "polyacrylonitrile",
    "carbon fiber",
    "carbon fiber bundle",
    "precursor fiber",
    "resin",
    "epoxy",
    "sizing agent",
    "cfrp",
    "炭素繊維",
    "前駆体",
    "ポリアクリロニトリル",
  ],
  "process": [
    "stabilization",
    "oxidation",
    "carbonization",
    "graphitization",
    "heat treatment",
    "surface treatment",
    "sizing",
    "drawing",
    "tension",
    "residence time",
    "atmosphere",
    "nitrogen atmosphere",
    "耐炎化",
    "酸化",
    "炭化",
    "黒鉛化",
    "表面処理",
    "サイジング",
  ],
  "structure": [
    "bundle",
    "tow",
    "filament",
    "laminate",
    "prepreg",
    "layer",
    "interface",
    "surface",
    "void",
    "crystallite",
    "orientation",
  ],
  "property": [
    "tensile strength",
    "modulus",
    "density",
    "defect",
    "interfacial shear strength",
    "resin impregnation",
    "adhesion",
    "strength variation",
    "引張強度",
    "弾性率",
    "欠陥",
    "ボイド",
  ],
  "application": [
    "aerospace",
    "pressure vessel",
    "automotive",
    "composite",
    "prepreg",
    "spring",
    "tank",
    "航空宇宙",
    "圧力容器",
    "複合材",
  ],
  "evaluation_method": [
    "tensile test",
    "modulus measurement",
    "sem",
    "xrd",
    "raman",
    "interfacial shear strength",
    "resin impregnation test",
  ],
  "problem_effect": [
    "defect suppression",
    "improved strength",
    "reduced variation",
    "improved adhesion",
    "improved impregnation",
    "void reduction",
  ],
}

NUMERICAL_PATTERNS = [
  re.compile(r"\b\d{2,4}\s*(?:to|~|〜|-)\s*\d{2,4}\s*(?:°|度|℃|C)\b", re.IGNORECASE),
  re.compile(r"\b\d{3,4}\s*(?:°|度|℃|C)\b", re.IGNORECASE),
  re.compile(r"\b\d+(?:\.\d+)?\s*(?:GPa|MPa|cN/dtex|Pa)\b", re.IGNORECASE),
  re.compile(r"\b\d+(?:\.\d+)?\s*(?:min|mins|minute|minutes|hr|hrs|hour|hours)\b", re.IGNORECASE),
  re.compile(r"\b\d+(?:\.\d+)?\s*(?:to|~|〜|-)\s*\d+(?:\.\d+)?\s*wt%\b", re.IGNORECASE),
  re.compile(r"\b\d+(?:\.\d+)?\s*%\b"),
]

PROBLEM_EFFECT_PATTERNS = [
  "improved",
  "reduced",
  "suppression",
  "enhanced",
  "lower variation",
  "改善",
  "低減",
  "抑制",
]


def _new_element_id(publication_number: str) -> str:
  return f"{publication_number}-{uuid.uuid4().hex[:8]}"


def split_claim_into_phrases(claim_text: str) -> list[str]:
  if not claim_text.strip():
    return []
  parts = [part.strip() for part in PHRASE_SPLIT_PATTERN.split(claim_text) if part.strip()]
  if not parts:
    return [claim_text.strip()]
  return parts


def _term_in_text(text: str, term: str) -> bool:
  normalized = term.lower()
  if normalized == "pan":
    return bool(re.search(r"\bpan\b", text, re.IGNORECASE))
  if any(ord(ch) > 127 for ch in term):
    return term in text
  return normalized in text.lower()


def normalize_claim_terms(phrase: str) -> list[str]:
  found: list[str] = []
  for terms in VOCABULARY.values():
    for term in terms:
      if _term_in_text(phrase, term) and term not in found:
        found.append(term)
  for pattern in NUMERICAL_PATTERNS:
    for match in pattern.finditer(phrase):
      snippet = match.group(0).strip()
      if snippet not in found:
        found.append(snippet)
  return found


def classify_claim_phrase(phrase: str) -> str:
  lowered = phrase.lower()
  scores: dict[str, int] = {}
  for element_type, terms in VOCABULARY.items():
    score = sum(1 for term in terms if _term_in_text(phrase, term))
    if score:
      scores[element_type] = score
  for pattern in NUMERICAL_PATTERNS:
    if pattern.search(phrase):
      scores["numerical_condition"] = scores.get("numerical_condition", 0) + 2
  if any(marker in lowered for marker in PROBLEM_EFFECT_PATTERNS):
    scores["problem_effect"] = scores.get("problem_effect", 0) + 1
  if not scores:
    return "unknown"
  return max(scores.items(), key=lambda item: item[1])[0]


def extract_numerical_conditions(text: str | None) -> list[str]:
  if not text:
    return []
  found: list[str] = []
  for pattern in NUMERICAL_PATTERNS:
    for match in pattern.finditer(text):
      snippet = match.group(0).strip()
      if snippet not in found:
        found.append(snippet)
  return found


def extract_problem_effect_terms(text: str | None) -> list[str]:
  if not text:
    return []
  found: list[str] = []
  lowered = text.lower()
  for marker in PROBLEM_EFFECT_PATTERNS:
    if marker.lower() in lowered or marker in text:
      found.append(marker)
  return found


def extract_claim_elements_from_claim(
  publication_number: str,
  claim_text: str,
  claim_number: str | None = None,
) -> list[ClaimElement]:
  elements: list[ClaimElement] = []
  for phrase in split_claim_into_phrases(claim_text):
    element_type = classify_claim_phrase(phrase)
    terms = normalize_claim_terms(phrase)
    if not terms and element_type == "unknown":
      continue
    elements.append(
      ClaimElement(
        element_id=_new_element_id(publication_number),
        publication_number=publication_number,
        claim_number=claim_number,
        element_type=element_type,
        element_text=phrase,
        normalized_terms=terms or [phrase[:80]],
        source_section="claims",
        evidence_snippet=phrase[:240],
        confidence=0.7 if terms else 0.45,
        support_status="claim_only",
      ),
    )
  return elements


def _limited_metadata_extraction(record: dict[str, Any]) -> list[ClaimElement]:
  publication_number = str(record.get("publication_number", ""))
  combined = " ".join(
    str(record.get(field, "") or "")
    for field in ("title", "abstract", "description")
  )
  elements: list[ClaimElement] = []
  for phrase in split_claim_into_phrases(combined)[:5]:
    element_type = classify_claim_phrase(phrase)
    terms = normalize_claim_terms(phrase)
    if not terms:
      continue
    elements.append(
      ClaimElement(
        element_id=_new_element_id(publication_number),
        publication_number=publication_number,
        claim_number=None,
        element_type=element_type,
        element_text=phrase,
        normalized_terms=terms,
        source_section="metadata",
        evidence_snippet=phrase[:240],
        confidence=0.35,
        support_status="metadata_only",
        notes=["Limited extraction from metadata because claims are unavailable"],
      ),
    )
  return elements


def extract_claim_elements_from_record(record: dict[str, Any]) -> dict[str, Any]:
  publication_number = str(record.get("publication_number", ""))
  claims_text = str(record.get("claims") or "").strip()
  independent_claims = list(record.get("independent_claims") or [])
  elements: list[ClaimElement] = []

  if claims_text:
    elements.extend(
      extract_claim_elements_from_claim(publication_number, claims_text, claim_number="all"),
    )
  for index, claim in enumerate(independent_claims, start=1):
    elements.extend(
      extract_claim_elements_from_claim(
        publication_number,
        str(claim),
        claim_number=str(index),
      ),
    )

  extraction_status = "full"
  if not elements:
    elements = _limited_metadata_extraction(record)
    extraction_status = "metadata_only" if elements else "skipped_no_claims"

  for num in extract_numerical_conditions(claims_text):
    elements.append(
      ClaimElement(
        element_id=_new_element_id(publication_number),
        publication_number=publication_number,
        claim_number=None,
        element_type="numerical_condition",
        element_text=num,
        normalized_terms=[num],
        source_section="claims",
        evidence_snippet=num,
        confidence=0.75,
        support_status="claim_only",
      ),
    )

  return {
    "publication_number": publication_number,
    "title": record.get("title"),
    "assignee": record.get("assignee"),
    "evidence_level": record.get("evidence_level"),
    "extraction_status": extraction_status,
    "elements": elements,
  }


def extract_claim_elements_for_records(records: list[dict[str, Any]]) -> dict[str, Any]:
  record_results: list[dict[str, Any]] = []
  all_elements: list[ClaimElement] = []
  for record in records:
    result = extract_claim_elements_from_record(record)
    record_results.append(result)
    all_elements.extend(result["elements"])
  return {
    "record_results": record_results,
    "elements": all_elements,
    "total_records": len(records),
    "records_with_claims": sum(
      1 for record in records if str(record.get("claims") or "").strip()
    ),
  }
