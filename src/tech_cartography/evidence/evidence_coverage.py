"""Evidence coverage evaluation for full text records."""

from __future__ import annotations

import re
from typing import Any

CLAIM_PATTERNS = [
  re.compile(r"(?im)^\s*(?:claim|claims)\s*1\b.*"),
  re.compile(r"(?im)^\s*1\.\s+.+"),
  re.compile(r"請求項\s*1"),
  re.compile(r"独立請求項\s*1"),
]

EXAMPLE_MARKERS = [
  "example",
  "examples",
  "embodiment",
  "実施例",
  "比較例",
]

PROPERTY_PATTERNS = [
  re.compile(r"\b\d+(?:\.\d+)?\s*(?:MPa|GPa|cN/dtex|Pa)\b", re.IGNORECASE),
  re.compile(r"\b\d+(?:\.\d+)?\s*%\b"),
  re.compile(r"tensile strength", re.IGNORECASE),
  re.compile(r"modulus", re.IGNORECASE),
  re.compile(r"elongation", re.IGNORECASE),
  re.compile(r"density", re.IGNORECASE),
]


def detect_independent_claims(claims_text: str | None) -> list[str]:
  if not claims_text:
    return []
  claims: list[str] = []
  for pattern in CLAIM_PATTERNS:
    match = pattern.search(claims_text)
    if match:
      snippet = match.group(0).strip()
      if snippet and snippet not in claims:
        claims.append(snippet)
  if not claims and claims_text.strip():
    first_line = claims_text.strip().splitlines()[0].strip()
    if first_line:
      claims.append(first_line)
  return claims


def extract_examples(description_text: str | None) -> str | None:
  if not description_text:
    return None
  lowered = description_text.lower()
  for marker in EXAMPLE_MARKERS:
    index = lowered.find(marker)
    if index >= 0:
      return description_text[index:index + 2000].strip()
  return None


def extract_measured_properties(text: str | None) -> list[str]:
  if not text:
    return []
  found: list[str] = []
  for pattern in PROPERTY_PATTERNS:
    for match in pattern.finditer(text):
      snippet = match.group(0).strip()
      if snippet and snippet not in found:
        found.append(snippet)
  return found


def evaluate_evidence_coverage(record: dict[str, Any]) -> dict[str, Any]:
  claims = str(record.get("claims") or "")
  description = str(record.get("description") or "")
  examples = str(record.get("examples") or extract_examples(description) or "")
  measured = list(record.get("measured_properties") or [])
  if not measured:
    measured = extract_measured_properties("\n".join([claims, description, examples]))

  independent_claims = detect_independent_claims(claims)
  coverage = {
    "has_claims": bool(claims.strip()),
    "has_independent_claim": bool(independent_claims),
    "has_description": bool(description.strip()),
    "has_examples": bool(examples.strip()),
    "has_measured_properties": bool(measured),
    "claims_length": len(claims),
    "description_length": len(description),
    "examples_length": len(examples),
    "measured_properties_count": len(measured),
  }
  coverage["evidence_level"] = assign_evidence_level(coverage)
  return coverage


def assign_evidence_level(coverage: dict[str, Any]) -> str:
  if (
    coverage.get("has_claims")
    and coverage.get("has_independent_claim")
    and coverage.get("has_description")
    and (coverage.get("has_examples") or coverage.get("has_measured_properties"))
  ):
    return "high_fulltext_evidence"
  if coverage.get("has_claims") and coverage.get("has_description"):
    return "medium_fulltext_evidence"
  if coverage.get("has_claims") or coverage.get("has_description"):
    return "low_fulltext_evidence"
  return "metadata_only"
