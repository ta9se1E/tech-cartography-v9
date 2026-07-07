"""Field-aware ranking match evidence for human-facing Study Demo displays."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from services_v9.research_value_theme_axes import (
  AXIS_COMPOSITION,
  AXIS_CONDITION,
  AXIS_HANDLING_PROPERTY,
  AXIS_INTERFACE_PROPERTY,
  AXIS_MATERIAL,
  AXIS_MECHANICAL_PROPERTY,
  AXIS_PROCESS,
  classify_theme_axis,
)
from services_v9.search_improvement_eligibility import reject_internal_token
from services_v9.study_demo_search.relevance_ranking import (
  CARBON_FIBER_RE,
  COMPOSITION_RE,
  SIZING_RE,
)

AXIS_LABELS_JA = {
  AXIS_COMPOSITION: "組成",
  AXIS_MATERIAL: "材料",
  AXIS_PROCESS: "工程",
  AXIS_CONDITION: "条件",
  AXIS_MECHANICAL_PROPERTY: "物性",
  AXIS_INTERFACE_PROPERTY: "界面",
  AXIS_HANDLING_PROPERTY: "取扱",
}

TERM_CHECKS: list[tuple[str, re.Pattern[str]]] = [
  ("carbon fiber", CARBON_FIBER_RE),
  ("sizing agent", SIZING_RE),
  ("aqueous", re.compile(r"\baqueous\b", re.I)),
  ("polyurethane", re.compile(r"\bpolyurethane\b", re.I)),
  ("ionic liquid", re.compile(r"\bionic[\s-]?liquid\b", re.I)),
  ("curing", re.compile(r"\bcuring\b", re.I)),
  ("drying", re.compile(r"\bdrying\b", re.I)),
]

INTERNAL_TOKEN_RE = re.compile(
  r"^(?P<term>[a-z0-9+ _-]+):(?P<field>title|abstract)$|^(?P<compound>[a-z0-9+_-]+)\+(?P<compound2>[a-z0-9+_-]+):(?P<field2>title|abstract)$",
  re.I,
)


def _title_abstract(signal: Mapping[str, Any]) -> tuple[str, str]:
  title = str(signal.get("title", "") or "")
  summary = str(signal.get("summary", "") or signal.get("abstract", "") or "")
  return title, summary


def _field_text(field: str, title: str, summary: str) -> str:
  if field == "title":
    return title
  if field in {"abstract", "summary"}:
    return summary
  return ""


def validate_match_field(term: str, field: str, title: str, summary: str) -> bool:
  normalized_field = "abstract" if field in {"abstract", "summary"} else field
  text = _field_text(normalized_field, title, summary)
  if not text.strip():
    return False
  needle = str(term or "").strip().lower()
  if not needle:
    return False
  if needle in {"carbon fiber", "carbon_fiber"}:
    return bool(CARBON_FIBER_RE.search(text))
  if needle in {"sizing agent", "sizing", "sizing_agent"}:
    return bool(SIZING_RE.search(text))
  for label, pattern in TERM_CHECKS:
    if label.replace(" ", "_") == needle.replace(" ", "_") or label == needle:
      return bool(pattern.search(text))
  return needle in text.lower()


def _parse_internal_token(token: str) -> tuple[str, str] | None:
  text = str(token or "").strip()
  if not text or ":" not in text:
    return None
  match = INTERNAL_TOKEN_RE.match(text)
  if not match:
    return None
  if match.group("compound"):
    left = str(match.group("compound") or "").replace("_", " ")
    right = str(match.group("compound2") or "").replace("_", " ")
    field = str(match.group("field2") or "title").lower()
    if field == "title":
      return f"{left} {right}".strip(), "title"
    return f"{left} {right}".strip(), "abstract"
  term = str(match.group("term") or "").replace("_", " ").replace("+", " ").strip()
  field = str(match.group("field") or "title").lower()
  return term, field


def _append_evidence(
  evidence: list[dict[str, Any]],
  *,
  term: str,
  field: str,
  title: str,
  summary: str,
  seen: set[tuple[str, str]],
) -> None:
  normalized_field = "abstract" if field in {"abstract", "summary"} else "title"
  key = (term.lower(), normalized_field)
  if key in seen:
    return
  matched = validate_match_field(term, normalized_field, title, summary)
  if not matched:
    return
  seen.add(key)
  evidence.append(
    {
      "term": term,
      "field": normalized_field,
      "matched": True,
      "source_text_verified": True,
    }
  )


def _scan_known_terms(title: str, summary: str, seen: set[tuple[str, str]]) -> list[dict[str, Any]]:
  found: list[dict[str, Any]] = []
  for label, pattern in TERM_CHECKS:
    if pattern.search(title):
      _append_evidence(found, term=label, field="title", title=title, summary=summary, seen=seen)
    if pattern.search(summary) and not pattern.search(title):
      _append_evidence(found, term=label, field="abstract", title=title, summary=summary, seen=seen)
  for match in COMPOSITION_RE.finditer(title):
    term = match.group(0).lower()
    if term not in {"sizing", "size agent"}:
      _append_evidence(found, term=term, field="title", title=title, summary=summary, seen=seen)
  for match in COMPOSITION_RE.finditer(summary):
    term = match.group(0).lower()
    if term in title.lower():
      continue
    _append_evidence(found, term=term, field="abstract", title=title, summary=summary, seen=seen)
  return found


def build_field_aware_match_evidence(signal: Mapping[str, Any]) -> list[dict[str, Any]]:
  title, summary = _title_abstract(signal)
  evidence: list[dict[str, Any]] = []
  seen: set[tuple[str, str]] = set()

  token_sources = (
    list(signal.get("matched_core_terms", []) or [])
    + list(signal.get("matched_process_terms", []) or [])
    + list(signal.get("matched_property_terms", []) or [])
  )
  for raw_token in token_sources:
    text = str(raw_token or "").strip()
    if "+" in text and ":" in text:
      body, field = text.rsplit(":", 1)
      for piece in body.split("+"):
        term = str(piece or "").replace("_", " ").strip()
        if term:
          _append_evidence(evidence, term=term, field=field, title=title, summary=summary, seen=seen)
      continue
    parsed = _parse_internal_token(text)
    if parsed:
      term, field = parsed
      _append_evidence(evidence, term=term, field=field, title=title, summary=summary, seen=seen)
      continue
    plain = str(raw_token or "").strip()
    if plain and not reject_internal_token(plain):
      if validate_match_field(plain, "title", title, summary):
        _append_evidence(evidence, term=plain, field="title", title=title, summary=summary, seen=seen)
      elif validate_match_field(plain, "abstract", title, summary):
        _append_evidence(evidence, term=plain, field="abstract", title=title, summary=summary, seen=seen)

  evidence.extend(_scan_known_terms(title, summary, seen))
  return evidence


def count_false_field_matches(evidence: Sequence[Mapping[str, Any]], signal: Mapping[str, Any]) -> dict[str, int]:
  title, summary = _title_abstract(signal)
  false_title = 0
  false_abstract = 0
  for item in evidence:
    term = str(item.get("term", "") or "")
    field = str(item.get("field", "") or "")
    if field == "title" and not validate_match_field(term, "title", title, summary):
      false_title += 1
    if field == "abstract" and not validate_match_field(term, "abstract", title, summary):
      false_abstract += 1
  return {"false_title_match_count": false_title, "false_abstract_match_count": false_abstract}


def build_human_ranking_summary(
  evidence: Sequence[Mapping[str, Any]],
  *,
  matched_theme_axes: Sequence[str] | None = None,
  tier: str = "",
) -> str:
  title_terms = [str(item.get("term", "")) for item in evidence if item.get("field") == "title"]
  abstract_terms = [str(item.get("term", "")) for item in evidence if item.get("field") == "abstract"]
  sentences: list[str] = []
  if title_terms:
    sentences.append(f"タイトルでは {' / '.join(title_terms)} が一致")
  if abstract_terms:
    sentences.append(f"概要では {' / '.join(abstract_terms)} の記載を確認しました")
  axis_labels = [AXIS_LABELS_JA.get(axis, axis) for axis in list(matched_theme_axes or [])[:3]]
  if axis_labels:
    sentences.append(f"{' / '.join(axis_labels)}のTheme軸をカバーするため")
  if str(tier or "") == "A":
    sentences.append("優先確認候補としています")
  elif str(tier or "") == "B":
    sentences.append("継続監視候補としています")
  elif sentences:
    sentences.append("背景確認候補としています")
  if not sentences:
    return "タイトル・概要の一致語とTheme軸に基づく候補です。"
  if len(sentences) == 1:
    return f"{sentences[0]}。"
  return f"{sentences[0]}し、{'、'.join(sentences[1:-1])}{('、' if len(sentences) > 2 else '')}{sentences[-1]}。"


def build_human_match_labels(
  evidence: Sequence[Mapping[str, Any]],
  *,
  matched_theme_axes: Sequence[str] | None = None,
  tier: str = "",
  data_basis: str = "",
) -> list[str]:
  labels: list[str] = []
  title_terms = [str(item.get("term", "")) for item in evidence if item.get("field") == "title"]
  abstract_terms = [str(item.get("term", "")) for item in evidence if item.get("field") == "abstract"]
  if title_terms:
    labels.append(f"- タイトル一致: {' / '.join(title_terms)}")
  if abstract_terms:
    labels.append(f"- 概要一致: {' / '.join(abstract_terms)}")
  axis_labels = [AXIS_LABELS_JA.get(axis, axis) for axis in list(matched_theme_axes or [])[:3]]
  if axis_labels:
    labels.append(f"- Themeとの一致: {' / '.join(axis_labels)}")
  if tier:
    labels.append(f"- Tier: {tier}")
  scope = "タイトル・概要" if data_basis == "title_abstract" else "タイトル"
  labels.append(f"- 分析範囲: {scope}")
  return labels


def build_ranking_basis_payload(
  signal: Mapping[str, Any],
  fact_sheet: Mapping[str, Any],
) -> dict[str, Any]:
  evidence = build_field_aware_match_evidence(signal)
  matched_theme_axes = list(fact_sheet.get("matched_theme_axes", []) or [])
  if not matched_theme_axes:
    matched_theme_axes = sorted(
      {
        classify_theme_axis(str(item.get("concept", "")))
        for item in list(fact_sheet.get("supported_concepts", []) or [])
        if classify_theme_axis(str(item.get("concept", "")))
      }
    )[:3]
  tier = str(signal.get("relevance_tier", "") or fact_sheet.get("relevance_tier", "") or "")
  summary_text = str(signal.get("summary", "") or "")
  data_basis = "title_abstract" if summary_text.strip() else "title_only"
  summary = build_human_ranking_summary(evidence, matched_theme_axes=matched_theme_axes, tier=tier)
  human_labels = build_human_match_labels(
    evidence,
    matched_theme_axes=matched_theme_axes,
    tier=tier,
    data_basis=data_basis,
  )
  raw_tokens = (
    list(signal.get("matched_core_terms", []) or [])
    + list(signal.get("matched_process_terms", []) or [])
    + list(signal.get("matched_property_terms", []) or [])
  )
  raw_evidence = [{"kind": "internal_token", "value": token} for token in raw_tokens if str(token).strip()]
  raw_evidence.extend(
    [
      {"kind": "score", "value": str(signal.get("relevance_score", ""))},
      {"kind": "tier", "value": tier},
      {"kind": "data_basis", "value": data_basis},
    ]
  )
  return {
    "summary": summary,
    "evidence": evidence,
    "human_labels": human_labels,
    "raw_evidence": raw_evidence,
    "field_validation": count_false_field_matches(evidence, signal),
  }


def simple_internal_token_count(ranking_basis: Mapping[str, Any]) -> int:
  joined = "\n".join(
    [
      str(ranking_basis.get("summary", "") or ""),
      "\n".join(str(item) for item in list(ranking_basis.get("human_labels", []) or [])),
    ]
  )
  patterns = (
    "keyword_match:",
    "exact_phrase:",
    "sizing:title",
    "carbon_fiber:title",
    "carbon_fiber+sizing:abstract",
    "data_basis:",
    "confidence:",
  )
  return sum(joined.count(pattern) for pattern in patterns)


__all__ = [
  "build_field_aware_match_evidence",
  "build_human_match_labels",
  "build_human_ranking_summary",
  "build_ranking_basis_payload",
  "count_false_field_matches",
  "simple_internal_token_count",
  "validate_match_field",
]
