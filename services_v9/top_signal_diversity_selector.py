"""Diverse Top 3 signal selection for research value cards."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from services_v9.research_signal_roles import (
  ROLE_FORMULATION,
  ROLE_INSUFFICIENT,
  ROLE_LOW,
  ROLE_NOVEL,
  ROLE_PROPERTY,
  ROLE_LABELS_JA,
  classify_signal_role,
)
from services_v9.research_value_fact_sheet import build_signal_fact_sheet
from services_v9.research_value_theme_axes import build_theme_axes

TIER_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}
PREFERRED_ROLES = (ROLE_FORMULATION, ROLE_PROPERTY, ROLE_NOVEL)


def _normalize_source(signal: Mapping[str, Any]) -> str:
  source = str(signal.get("source_type", "") or signal.get("type", "") or "").lower()
  return "web" if source == "web_company" else source


def _relevance_score(signal: Mapping[str, Any]) -> float:
  raw = signal.get("relevance_score", signal.get("integrated_relevance_score", 0))
  try:
    return float(raw or 0)
  except (TypeError, ValueError):
    return 0.0


def _selection_utility(
  signal: Mapping[str, Any],
  *,
  role_code: str,
  selected_roles: set[str],
  selected_sources: set[str],
  covered_axes: set[str],
  theme_axes: Mapping[str, Any],
) -> float:
  relevance = _relevance_score(signal) / 100.0
  role_gain = 1.0 if role_code not in selected_roles else 0.0
  source = _normalize_source(signal)
  source_gain = 1.0 if source not in selected_sources else 0.2
  fact = build_signal_fact_sheet(signal, theme_axes)
  axis_gain = len(set(fact.get("matched_theme_axes", [])) - covered_axes) / 5.0
  evidence_gain = min(len(fact.get("supported_concepts", [])), 5) / 5.0
  preferred_bonus = 0.15 if role_code in PREFERRED_ROLES else 0.0
  penalty = 0.0
  if role_code in {ROLE_LOW, ROLE_INSUFFICIENT}:
    penalty = 0.5
  return relevance * 0.50 + role_gain * 0.20 + source_gain * 0.10 + axis_gain * 0.15 + evidence_gain * 0.05 + preferred_bonus - penalty


def select_diverse_top_signals(
  signals: Sequence[Mapping[str, Any]],
  theme: Mapping[str, Any],
  *,
  limit: int = 3,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
  theme_axes = build_theme_axes(theme)
  ranked = sorted(
    list(signals),
    key=lambda item: (
      TIER_ORDER.get(str(item.get("relevance_tier", "D")), 99),
      -_relevance_score(item),
      str(item.get("title", "")),
    ),
  )
  selected: list[dict[str, Any]] = []
  selected_roles: set[str] = set()
  selected_sources: set[str] = set()
  covered_axes: set[str] = set()
  selection_notes: list[str] = []

  for _ in range(limit):
    best_signal: dict[str, Any] | None = None
    best_role: dict[str, Any] | None = None
    best_score = -1.0
    for signal in ranked:
      signal_id = str(signal.get("signal_id", "") or signal.get("id", "") or "")
      if any(str(signal.get("signal_id", "") or signal.get("id", "")) == str(item.get("signal_id", "") or item.get("id", "")) for item in selected):
        continue
      role = classify_signal_role(signal, theme_axes=theme_axes)
      score = _selection_utility(
        signal,
        role_code=str(role.get("code", "")),
        selected_roles=selected_roles,
        selected_sources=selected_sources,
        covered_axes=covered_axes,
        theme_axes=theme_axes,
      )
      if score > best_score:
        best_score = score
        best_signal = dict(signal)
        best_role = role
    if not best_signal or not best_role:
      break
    fact = build_signal_fact_sheet(best_signal, theme_axes)
    selected.append(
      {
        "signal": best_signal,
        "role": best_role,
        "fact_sheet": fact,
        "selection_score": round(best_score, 4),
      }
    )
    selected_roles.add(str(best_role.get("code", "")))
    selected_sources.add(_normalize_source(best_signal))
    covered_axes.update(fact.get("matched_theme_axes", []) or [])
    selection_notes.append(
      f"{best_signal.get('title', '')[:48]} -> {best_role.get('label_ja', '')} ({best_score:.3f})"
    )

  metadata = {
    "selected_count": len(selected),
    "role_codes": [str(item["role"].get("code", "")) for item in selected],
    "role_labels_ja": [str(item["role"].get("label_ja", "")) for item in selected],
    "source_types": [_normalize_source(item["signal"]) for item in selected],
    "selection_notes": selection_notes,
    "theme_axes": theme_axes,
  }
  return selected, metadata


__all__ = ["select_diverse_top_signals", "PREFERRED_ROLES", "ROLE_LABELS_JA"]
