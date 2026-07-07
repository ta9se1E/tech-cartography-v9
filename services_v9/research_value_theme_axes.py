"""Theme axis extraction for deterministic research value synthesis."""

from __future__ import annotations

import re
from typing import Any, Mapping

AXIS_MATERIAL = "material"
AXIS_COMPOSITION = "composition"
AXIS_PROCESS = "process"
AXIS_CONDITION = "condition"
AXIS_HANDLING_PROPERTY = "handling_property"
AXIS_INTERFACE_PROPERTY = "interface_property"
AXIS_MECHANICAL_PROPERTY = "mechanical_property"
AXIS_EVALUATION = "evaluation"
AXIS_APPLICATION = "application"
AXIS_RISK = "risk_or_limitation"

DOMAIN_AXIS_HINTS: dict[str, tuple[str, ...]] = {
  AXIS_MATERIAL: ("carbon fiber", "pan", "炭素繊維", "サイジング", "sizing agent", "tow", "prepreg"),
  AXIS_COMPOSITION: (
    "composition", "resin", "polyurethane", "epoxy", "ionic liquid", "aqueous", "emulsifier",
    "樹脂", "主成分", "添加剤", "溶媒", "配合比", "polymer",
  ),
  AXIS_PROCESS: (
    "preparation", "coating", "application", "sizing", "treatment", "付与", "塗布", "乾燥", "硬化",
    "curing", "drying",
  ),
  AXIS_CONDITION: ("concentration", "temperature", "time", "atmosphere", "濃度", "温度", "時間", "雰囲気", "wt%"),
  AXIS_HANDLING_PROPERTY: (
    "tow integrity", "spreadability", "fuzz", "abrasion", "wear-resistant", "handling",
    "集束性", "開繊性", "毛羽", "耐擦過性", "含浸",
  ),
  AXIS_INTERFACE_PROPERTY: ("interfacial", "adhesion", "interface", "wetting", "界面", "接着", "impregnation"),
  AXIS_MECHANICAL_PROPERTY: (
    "tensile", "modulus", "strength", "mechanical properties", "引張", "弾性率", "強度",
  ),
  AXIS_EVALUATION: ("evaluation", "test", "measurement", "評価", "試験", "characterization"),
  AXIS_APPLICATION: ("matrix", "composite", "thermoplastic", "towpreg", "複合材料", "用途"),
  AXIS_RISK: ("brittleness", "defect", "limitation", "exclude", "除外", "high-brittleness"),
}


def _collect_theme_text(theme: Mapping[str, Any]) -> str:
  parts: list[str] = [
    str(theme.get("name", "") or ""),
    str(theme.get("description", "") or ""),
  ]
  keywords = dict(theme.get("keywords", {}) or {})
  for values in keywords.values():
    if isinstance(values, list):
      parts.extend(str(item) for item in values)
    elif values:
      parts.append(str(values))
  return " ".join(parts).lower()


def normalize_theme_terms(theme: Mapping[str, Any]) -> list[str]:
  blob = _collect_theme_text(theme)
  terms: list[str] = []
  for hints in DOMAIN_AXIS_HINTS.values():
    for hint in hints:
      if hint.lower() in blob and hint not in terms:
        terms.append(hint)
  return terms


def classify_theme_axis(term: str) -> str:
  lowered = term.lower()
  for axis, hints in DOMAIN_AXIS_HINTS.items():
    if any(hint in lowered or lowered in hint for hint in hints):
      return axis
  return AXIS_APPLICATION


def build_axis_priority(theme: Mapping[str, Any]) -> list[str]:
  blob = _collect_theme_text(theme)
  scores: dict[str, int] = {axis: 0 for axis in DOMAIN_AXIS_HINTS}
  for axis, hints in DOMAIN_AXIS_HINTS.items():
    for hint in hints:
      if hint.lower() in blob:
        scores[axis] += 1
  ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
  return [axis for axis, count in ordered if count > 0] or [
    AXIS_MATERIAL,
    AXIS_COMPOSITION,
    AXIS_PROCESS,
    AXIS_CONDITION,
    AXIS_HANDLING_PROPERTY,
  ]


def build_theme_axes(theme: Mapping[str, Any]) -> dict[str, Any]:
  priority = build_axis_priority(theme)
  terms = normalize_theme_terms(theme)
  grouped: dict[str, list[str]] = {axis: [] for axis in DOMAIN_AXIS_HINTS}
  for term in terms:
    grouped[classify_theme_axis(term)].append(term)
  return {
    "theme_id": str(theme.get("theme_id", "") or ""),
    "theme_name": str(theme.get("name", "") or ""),
    "priority_axes": priority,
    "axis_terms": {key: values for key, values in grouped.items() if values},
    "exclude_terms": _extract_exclude_terms(theme),
  }


def _extract_exclude_terms(theme: Mapping[str, Any]) -> list[str]:
  keywords = dict(theme.get("keywords", {}) or {})
  excludes: list[str] = []
  for key in ("exclude_en", "exclude_ja"):
    values = keywords.get(key, [])
    if isinstance(values, list):
      excludes.extend(str(item) for item in values)
  return excludes


def axis_label_ja(axis: str) -> str:
  return {
    AXIS_MATERIAL: "材料",
    AXIS_COMPOSITION: "組成",
    AXIS_PROCESS: "工程",
    AXIS_CONDITION: "条件",
    AXIS_HANDLING_PROPERTY: "取扱物性",
    AXIS_INTERFACE_PROPERTY: "界面",
    AXIS_MECHANICAL_PROPERTY: "力学物性",
    AXIS_EVALUATION: "評価",
    AXIS_APPLICATION: "用途",
    AXIS_RISK: "制約",
  }.get(axis, axis)


def tokenize_document(text: str) -> set[str]:
  return {token for token in re.findall(r"[a-z0-9\u3040-\u30ff\u4e00-\u9fff]{3,}", text.lower())}


__all__ = [
  "build_axis_priority",
  "build_theme_axes",
  "classify_theme_axis",
  "normalize_theme_terms",
  "axis_label_ja",
  "tokenize_document",
]
