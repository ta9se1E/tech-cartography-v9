"""Role taxonomy for research value synthesis."""

from __future__ import annotations

import re
from typing import Any, Mapping

ROLE_FORMULATION = "formulation_process_candidate"
ROLE_PROPERTY = "property_evidence"
ROLE_NOVEL = "novel_formulation_hypothesis"
ROLE_MECHANISM = "mechanism_interface_hypothesis"
ROLE_COMPARISON = "comparison_benchmark"
ROLE_EVALUATION = "evaluation_method"
ROLE_SCALEUP = "scaleup_manufacturing"
ROLE_BACKGROUND = "background_review"
ROLE_LOW = "low_relevance"
ROLE_INSUFFICIENT = "insufficient_information"

ROLE_LABELS_JA = {
  ROLE_FORMULATION: "処方・工程候補",
  ROLE_PROPERTY: "物性エビデンス",
  ROLE_NOVEL: "新規処方仮説",
  ROLE_MECHANISM: "作用機構・界面仮説",
  ROLE_COMPARISON: "比較・基準候補",
  ROLE_EVALUATION: "評価方法候補",
  ROLE_SCALEUP: "製造・スケールアップ候補",
  ROLE_BACKGROUND: "背景整理",
  ROLE_LOW: "低関連",
  ROLE_INSUFFICIENT: "情報不足",
}

_FORMULATION_TERMS = (
  "sizing", "composition", "preparation", "aqueous", "resin", "coating", "treatment",
  "polyurethane", "epoxy", "wear-resistant", "brittleness",
)
_PROPERTY_TERMS = (
  "mechanical properties", "tensile", "modulus", "interfacial", "adhesion", "impregnation",
  "abrasion", "fuzz", "strength", "towpreg",
)
_NOVEL_TERMS = ("novel", "ionic liquid", "hybrid", "composite sizing", "bio-based", "waterborne", "water-based")
_MECHANISM_TERMS = ("interface", "interphase", "wetting", "surface energy", "functional group", "chemical interaction")
_BACKGROUND_TERMS = ("review", "overview", "survey", "state of the art")


def _blob(signal: Mapping[str, Any]) -> str:
  return f"{signal.get('title', '')} {signal.get('summary', '')}".lower()


def _contains_any(blob: str, terms: tuple[str, ...]) -> list[str]:
  return [term for term in terms if term in blob]


def classify_signal_role(
  signal: Mapping[str, Any],
  *,
  theme_axes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
  source_type = str(signal.get("source_type", "") or signal.get("type", "") or "").lower()
  if source_type == "web_company":
    source_type = "web"
  blob = _blob(signal)
  title = str(signal.get("title", "") or "")
  excludes = list((theme_axes or {}).get("exclude_terms", []) or [])
  negative_hits = [term for term in excludes if term and term.lower() in blob]
  if negative_hits and not any(token in blob for token in ("sizing", "carbon fiber", "サイジング")):
    return {
      "code": ROLE_LOW,
      "label_ja": ROLE_LABELS_JA[ROLE_LOW],
      "confidence": "high",
      "evidence_terms": negative_hits,
      "reason": "除外語中心のため低関連",
    }

  novel_hits = _contains_any(blob, _NOVEL_TERMS)
  formulation_hits = _contains_any(blob, _FORMULATION_TERMS)
  property_hits = _contains_any(blob, _PROPERTY_TERMS)
  mechanism_hits = _contains_any(blob, _MECHANISM_TERMS)
  background_hits = _contains_any(blob, _BACKGROUND_TERMS)

  if background_hits and not formulation_hits and not property_hits:
    return {
      "code": ROLE_BACKGROUND,
      "label_ja": ROLE_LABELS_JA[ROLE_BACKGROUND],
      "confidence": "medium",
      "evidence_terms": background_hits,
      "reason": "review/overview系の背景整理候補",
    }

  if source_type == "patent" and novel_hits and any(term in blob for term in ("ionic liquid", "hybrid", "composite", "novel")):
    return {
      "code": ROLE_NOVEL,
      "label_ja": ROLE_LABELS_JA[ROLE_NOVEL],
      "confidence": "high",
      "evidence_terms": novel_hits + formulation_hits,
      "reason": "新規処方語とTheme処方軸が一致",
    }

  if source_type == "patent" and formulation_hits:
    return {
      "code": ROLE_FORMULATION,
      "label_ja": ROLE_LABELS_JA[ROLE_FORMULATION],
      "confidence": "high",
      "evidence_terms": formulation_hits,
      "reason": "特許タイトル/概要に処方・工程語が一致",
    }

  if source_type == "paper" and property_hits:
    return {
      "code": ROLE_PROPERTY,
      "label_ja": ROLE_LABELS_JA[ROLE_PROPERTY],
      "confidence": "high",
      "evidence_terms": property_hits,
      "reason": "論文が力学/界面物性を扱う",
    }

  if mechanism_hits:
    return {
      "code": ROLE_MECHANISM,
      "label_ja": ROLE_LABELS_JA[ROLE_MECHANISM],
      "confidence": "medium",
      "evidence_terms": mechanism_hits,
      "reason": "界面・作用機構語が一致",
    }

  if "comparison" in blob or "benchmark" in blob or "versus" in blob:
    return {
      "code": ROLE_COMPARISON,
      "label_ja": ROLE_LABELS_JA[ROLE_COMPARISON],
      "confidence": "medium",
      "evidence_terms": ["comparison"],
      "reason": "比較・基準候補",
    }

  if not title.strip() or len(blob.strip()) < 20:
    return {
      "code": ROLE_INSUFFICIENT,
      "label_ja": ROLE_LABELS_JA[ROLE_INSUFFICIENT],
      "confidence": "low",
      "evidence_terms": [],
      "reason": "title/abstract情報不足",
    }

  return {
    "code": ROLE_BACKGROUND,
    "label_ja": ROLE_LABELS_JA[ROLE_BACKGROUND],
    "confidence": "low",
    "evidence_terms": formulation_hits + property_hits,
    "reason": "直接一致が弱い背景候補",
  }


__all__ = [
  "ROLE_FORMULATION",
  "ROLE_PROPERTY",
  "ROLE_NOVEL",
  "ROLE_LABELS_JA",
  "classify_signal_role",
]
