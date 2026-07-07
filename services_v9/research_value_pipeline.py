"""Orchestration for deterministic research value Top 3 bundle."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from services_v9.research_value_fact_sheet import build_signal_fact_sheet, validate_fact_sheet
from services_v9.research_value_quality import validate_top3_bundle
from services_v9.research_value_synthesizer import synthesize_research_value_output
from services_v9.research_value_theme_axes import build_theme_axes
from services_v9.top_signal_diversity_selector import select_diverse_top_signals


def build_research_value_top3(
  signals: Sequence[Mapping[str, Any]],
  theme: Mapping[str, Any],
  *,
  limit: int = 3,
) -> dict[str, Any]:
  selected, selection_meta = select_diverse_top_signals(signals, theme, limit=limit)
  bundle: list[dict[str, Any]] = []
  for index, item in enumerate(selected, start=1):
    signal = dict(item.get("signal", {}) or {})
    role = dict(item.get("role", {}) or {})
    fact_sheet = dict(item.get("fact_sheet", {}) or build_signal_fact_sheet(signal, build_theme_axes(theme)))
    fact_errors = validate_fact_sheet(fact_sheet)
    output = synthesize_research_value_output(signal, role=role, fact_sheet=fact_sheet)
    bundle.append(
      {
        "rank": index,
        "signal": signal,
        "role": role,
        "fact_sheet": fact_sheet,
        "output": output,
        "fact_sheet_errors": fact_errors,
        "selection_score": item.get("selection_score"),
      }
    )
  quality = validate_top3_bundle(bundle)
  return {
    "items": bundle,
    "selection": selection_meta,
    "quality": quality,
    "theme_axes": selection_meta.get("theme_axes", {}),
  }


__all__ = ["build_research_value_top3"]
