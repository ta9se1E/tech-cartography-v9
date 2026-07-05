"""Study demo relevance tiering and ranking for integrated search signals."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

TIER_A = "A"
TIER_B = "B"
TIER_C = "C"
TIER_D = "D"
TIER_ORDER = {TIER_A: 0, TIER_B: 1, TIER_C: 2, TIER_D: 3}

CARBON_FIBER_RE = re.compile(
  r"\b(carbon[\s-]?fib(?:er|re)s?|carbon[\s-]?fibres?)\b",
  re.I,
)
SIZING_RE = re.compile(r"\b(sizing(?:[\s-]?agent)?|size[\s-]?agent)\b", re.I)
PAN_RE = re.compile(
  r"\b(pan[\s-]based|pan[\s-]precursor|polyacrylonitrile|pan[\s-]carbon[\s-]?fib(?:er|re)s?)\b",
  re.I,
)
PITCH_RE = re.compile(
  r"\b(pitch[\s-]based|asphalt[\s-]based|mesophase[\s-]pitch|isotropic[\s-]pitch|asphalt[\s-]based[\s-]carbon)\b",
  re.I,
)
TIER_B_MECHANISM_RE = re.compile(
  r"\b("
  r"interfac(?:e|ial)|impregnation|surface[\s-]treatment|towpreg|tow[\s-]preg|"
  r"fuzz|abrasion|adhesion|spreadability|sizing[\s-]amount|add[\s-]on"
  r")\b",
  re.I,
)
COMPOSITION_RE = re.compile(
  r"\b(epoxy|polyurethane|polyamide|polyester|modified[\s-]polyolefin|aqueous|"
  r"sizing[\s-]amount|add[\s-]on|drying|curing|fuzz|abrasion|spreadability|"
  r"impregnation|interfacial[\s-]adhesion|tensile[\s-]modulus)\b",
  re.I,
)
NEGATIVE_TITLE_RE = re.compile(
  r"\b(paper[\s-]sizing|starch[\s-]sizing|textile[\s-]fabric|polyester[\s-]fiber[\s-]fabric|"
  r"antibacterial[\s-]fabric|ultraviolet[\s-]resistant|bamboo[\s-]fiber|"
  r"battery[\s-]electrode|activated[\s-]carbon|carbon[\s-]black|cement)\b",
  re.I,
)
NEGATIVE_BODY_RE = re.compile(
  r"\b(paper[\s-]sizing|starch[\s-]sizing|textile|fabric|bamboo|battery[\s-]electrode|"
  r"activated[\s-]carbon|carbon[\s-]black|cement)\b",
  re.I,
)
BACKGROUND_RE = re.compile(
  r"\b(handbook|general[\s-]review|composite[\s-]materials|carbon[\s-]fibers?\s+and\s+their|"
  r"recycling|pyrolysis|manufacturing[\s-]overview|structural[\s-]composites)\b",
  re.I,
)
COMPOSITE_RE = re.compile(r"\b(composite|carbon[\s-]?fib(?:er|re)s?|cf[\s\-/]?\w+)\b", re.I)


def _text(title: str, summary: str) -> tuple[str, str, str]:
  title_l = str(title or "").strip()
  summary_l = str(summary or "").strip()
  combined = f"{title_l} {summary_l}".strip()
  return title_l, summary_l, combined


def _find_matches(pattern: re.Pattern[str], text: str) -> list[str]:
  return sorted({match.group(0).lower() for match in pattern.finditer(text or "")})


def _context_from_provenance(query_provenance: Mapping[str, Any]) -> dict[str, Any]:
  theme = str(query_provenance.get("theme", "") or "")
  exact_phrase = str(query_provenance.get("exact_phrase", "") or "").strip()
  keywords_en = str(query_provenance.get("keywords_en", "") or "")
  keywords_ja = str(query_provenance.get("keywords_ja", "") or "")
  exclude = str(query_provenance.get("exclude_keywords", "") or "")
  pan_target = "pan" in theme.lower() or "pan系" in theme
  return {
    "theme": theme,
    "exact_phrase": exact_phrase,
    "pan_target": pan_target,
    "exclude_terms": [part.strip().lower() for part in re.split(r"[,、\n]+", exclude) if part.strip()],
    "keywords_blob": f"{keywords_en} {keywords_ja}".lower(),
  }


def _score_signal(signal: Mapping[str, Any], ctx: Mapping[str, Any]) -> dict[str, Any]:
  title, summary, combined = _text(str(signal.get("title", "") or ""), str(signal.get("summary", "") or ""))
  title_l = title.lower()
  summary_l = summary.lower()
  combined_l = combined.lower()

  breakdown: dict[str, float] = {}
  matched_core: list[str] = []
  matched_material: list[str] = []
  matched_process: list[str] = []
  matched_property: list[str] = []
  matched_negative: list[str] = []

  score = 0.0
  exact_phrase = str(ctx.get("exact_phrase", "") or "").strip().lower()
  if exact_phrase:
    if exact_phrase in title_l:
      score += 30
      breakdown["exact_phrase_title"] = 30
      matched_core.append("exact_phrase:title")
    elif exact_phrase in summary_l:
      score += 20
      breakdown["exact_phrase_abstract"] = 20
      matched_core.append("exact_phrase:abstract")

  if CARBON_FIBER_RE.search(title_l):
    score += 15
    breakdown["carbon_fiber_title"] = 15
    matched_core.append("carbon_fiber:title")
  if SIZING_RE.search(title_l):
    score += 15
    breakdown["sizing_title"] = 15
    matched_core.append("sizing:title")
  if CARBON_FIBER_RE.search(title_l) and SIZING_RE.search(title_l):
    score += 15
    breakdown["carbon_fiber_and_sizing_title"] = 15
  if CARBON_FIBER_RE.search(summary_l) and SIZING_RE.search(summary_l):
    if not (CARBON_FIBER_RE.search(title_l) and SIZING_RE.search(title_l)):
      score += 10
      breakdown["carbon_fiber_and_sizing_abstract"] = 10
      matched_core.append("carbon_fiber+sizing:abstract")

  target_material_match = ""
  target_material_mismatch = ""
  if PAN_RE.search(combined_l):
    score += 12
    breakdown["pan_match"] = 12
    target_material_match = "pan"
    matched_material.append("pan")
  if ctx.get("pan_target") and PITCH_RE.search(combined_l):
    score -= 12
    breakdown["pitch_mismatch"] = -12
    target_material_mismatch = "pitch/asphalt"
    matched_material.append("pitch/asphalt")

  for term in _find_matches(COMPOSITION_RE, title_l):
    matched_process.append(f"{term}:title")
  comp_title_count = len(_find_matches(COMPOSITION_RE, title_l))
  if comp_title_count:
    breakdown["composition_title"] = 8 * comp_title_count
    score += breakdown["composition_title"]
  comp_abs = [t for t in _find_matches(COMPOSITION_RE, summary_l) if t not in title_l]
  if comp_abs:
    breakdown["composition_abstract"] = 4 * len(comp_abs)
    score += breakdown["composition_abstract"]
    matched_property.extend(f"{term}:abstract" for term in comp_abs)

  for term in ctx.get("exclude_terms", []):
    if term and term in title_l:
      score -= 35
      breakdown["exclude_title"] = breakdown.get("exclude_title", 0) - 35
      matched_negative.append(term)

  for term in _find_matches(NEGATIVE_TITLE_RE, title_l):
    score -= 40
    matched_negative.append(term)
    breakdown["negative_title"] = breakdown.get("negative_title", 0) - 40
  for term in _find_matches(NEGATIVE_BODY_RE, summary_l):
    if term not in title_l:
      score -= 12
      matched_negative.append(f"{term}:abstract")
      breakdown["negative_abstract"] = breakdown.get("negative_abstract", 0) - 12

  if BACKGROUND_RE.search(combined_l) and not (CARBON_FIBER_RE.search(title_l) and SIZING_RE.search(title_l)):
    score -= 18
    breakdown["background_penalty"] = -18

  metadata = dict(signal.get("metadata", {}) or {})
  source_type = str(signal.get("source_type", "") or "")
  aux_bonus = 0.0
  if source_type == "paper":
    cited = metadata.get("cited_by_count")
    if cited and CARBON_FIBER_RE.search(combined_l):
      aux_bonus = min(2.0, float(cited) / 500.0)
  elif source_type == "web_company":
    raw_score = metadata.get("score")
    if raw_score and CARBON_FIBER_RE.search(combined_l):
      aux_bonus = min(2.0, float(raw_score or 0) / 50.0)
  if aux_bonus:
    breakdown["auxiliary_source_bonus"] = aux_bonus
    score += aux_bonus

  has_cf = bool(CARBON_FIBER_RE.search(combined_l))
  has_sizing = bool(SIZING_RE.search(combined_l))
  has_mechanism = bool(TIER_B_MECHANISM_RE.search(combined_l))
  has_composite = bool(COMPOSITE_RE.search(combined_l))
  strong_negative_title = bool(NEGATIVE_TITLE_RE.search(title_l)) or any(
    term in title_l for term in ctx.get("exclude_terms", [])
  )

  tier = TIER_C
  title_cf_and_sizing = bool(CARBON_FIBER_RE.search(title_l) and SIZING_RE.search(title_l))
  abstract_cf_and_sizing = bool(
    CARBON_FIBER_RE.search(summary_l) and SIZING_RE.search(summary_l) and SIZING_RE.search(title_l)
  )
  exact_phrase_hit = bool(exact_phrase and exact_phrase in combined_l)
  if strong_negative_title and not (has_cf and has_sizing):
    tier = TIER_D
  elif has_cf and has_sizing and (title_cf_and_sizing or exact_phrase_hit or abstract_cf_and_sizing):
    if ctx.get("pan_target") and PITCH_RE.search(title_l):
      tier = TIER_B
    else:
      tier = TIER_A
  elif has_cf and has_mechanism:
    tier = TIER_B
  elif has_composite or has_cf:
    tier = TIER_C
  elif strong_negative_title or matched_negative:
    tier = TIER_D
  else:
    tier = TIER_D

  if tier == TIER_D:
    capped = min(score, 15.0)
  elif tier == TIER_C:
    capped = min(max(score, 10.0), 45.0)
  elif tier == TIER_B:
    capped = max(score, 35.0)
  else:
    capped = max(score, 55.0)
  if capped != score:
    breakdown["tier_adjustment"] = round(capped - score, 4)
    score = capped

  score = max(0.0, min(100.0, score))
  breakdown_total = round(sum(breakdown.values()), 4)
  if abs(breakdown_total - score) > 0.01:
    breakdown["rounding_adjustment"] = round(score - breakdown_total, 4)
  reason = _build_reason(
    tier=tier,
    has_cf=has_cf,
    has_sizing=has_sizing,
    matched_process=matched_process,
    matched_property=matched_property,
    target_material_mismatch=target_material_mismatch,
    background=bool(BACKGROUND_RE.search(combined_l)),
  )

  return {
    "relevance_tier": tier,
    "source_raw_score": round(score, 4),
    "matched_core_terms": matched_core,
    "matched_material_terms": matched_material,
    "matched_process_terms": matched_process,
    "matched_property_terms": matched_property,
    "matched_negative_terms": matched_negative,
    "target_material_match": target_material_match,
    "target_material_mismatch": target_material_mismatch,
    "score_breakdown": breakdown,
    "relevance_reason": reason,
  }


def _build_reason(
  *,
  tier: str,
  has_cf: bool,
  has_sizing: bool,
  matched_process: Sequence[str],
  matched_property: Sequence[str],
  target_material_mismatch: str,
  background: bool,
) -> str:
  if tier == TIER_A:
    terms = ", ".join(sorted(set(matched_process + matched_property))[:4])
    suffix = f"、{terms}が一致" if terms else ""
    mismatch = f"（対象材料不一致: {target_material_mismatch}）" if target_material_mismatch else ""
    return (
      "タイトルにcarbon fiberとsizing agentが存在し、テーマへの直接関連が高いため直接関連"
      f"{suffix}{mismatch}"
    )
  if tier == TIER_B:
    if target_material_mismatch:
      return (
        "サイジング技術としては関連するが、PAN系以外の炭素繊維（pitch/asphalt系）の可能性があり"
        "対象材料不一致として順位を下げた補助的証拠"
      )
    return "炭素繊維の界面・含浸・評価特性など作用機構へ直接関連する補助的証拠"
  if tier == TIER_C:
    if background:
      return "炭素繊維複合材の一般論として関連するが、サイジング剤への直接言及がないため背景資料"
    return "炭素繊維複合材の背景理解に有効だが、サイジング条件の直接証拠ではない背景資料"
  return "テーマから外れる語句が中心で、炭素繊維サイジングへの実質的関連が低い"


def _normalize_within_source(scored: list[dict[str, Any]]) -> None:
  by_source: dict[str, list[dict[str, Any]]] = {}
  for item in scored:
    source = str(item.get("source_type", "") or "unknown")
    by_source.setdefault(source, []).append(item)
  for items in by_source.values():
    values = [float(item["source_raw_score"]) for item in items]
    min_v = min(values)
    max_v = max(values)
    for item in items:
      raw = float(item["source_raw_score"])
      if max_v > min_v:
        normalized = 100.0 * (raw - min_v) / (max_v - min_v)
      else:
        normalized = raw
      item["source_normalized_score"] = round(normalized, 2)
      tier = str(item.get("relevance_tier", TIER_C))
      tier_floor = {TIER_A: 70.0, TIER_B: 40.0, TIER_C: 15.0, TIER_D: 0.0}[tier]
      tier_cap = {TIER_A: 100.0, TIER_B: 69.0, TIER_C: 39.0, TIER_D: 14.0}[tier]
      integrated = min(tier_cap, tier_floor + normalized * (tier_cap - tier_floor) / 100.0)
      item["integrated_relevance_score"] = round(integrated, 2)
      item["relevance_score"] = int(round(integrated))


def apply_relevance_ranking(
  signals: Sequence[Mapping[str, Any]],
  *,
  query_provenance: Mapping[str, Any],
) -> list[dict[str, Any]]:
  ctx = _context_from_provenance(query_provenance)
  enriched: list[dict[str, Any]] = []
  for signal in signals:
    item = dict(signal)
    scored = _score_signal(item, ctx)
    item.update(scored)
    enriched.append(item)
  _normalize_within_source(enriched)
  enriched.sort(
    key=lambda row: (
      TIER_ORDER.get(str(row.get("relevance_tier", TIER_D)), 99),
      -float(row.get("integrated_relevance_score", 0) or 0),
      -float(row.get("source_raw_score", 0) or 0),
      str(row.get("title", "") or ""),
    ),
  )
  return enriched


def filter_ranked_signals(
  signals: Sequence[Mapping[str, Any]],
  *,
  tiers: Sequence[str] | None = None,
  min_score: int = 0,
  source_types: Sequence[str] | None = None,
  pan_only: bool = False,
  include_pitch: bool = True,
  include_background: bool = True,
) -> list[dict[str, Any]]:
  allowed_tiers = set(tiers or {TIER_A, TIER_B, TIER_C})
  allowed_sources = set(source_types or [])
  out: list[dict[str, Any]] = []
  for signal in signals:
    tier = str(signal.get("relevance_tier", TIER_D))
    if tier not in allowed_tiers:
      continue
    if tier == TIER_C and not include_background:
      continue
    if int(signal.get("relevance_score", 0) or 0) < min_score:
      continue
    source_type = str(signal.get("source_type", "") or "")
    if allowed_sources and source_type not in allowed_sources:
      continue
    mismatch = str(signal.get("target_material_mismatch", "") or "")
    if pan_only and mismatch:
      continue
    if not include_pitch and mismatch:
      continue
    out.append(dict(signal))
  return out


def group_signals_by_tier(signals: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
  grouped = {TIER_A: [], TIER_B: [], TIER_C: [], TIER_D: []}
  for signal in signals:
    tier = str(signal.get("relevance_tier", TIER_C))
    grouped.setdefault(tier, []).append(dict(signal))
  return grouped


def enrich_integrated_signals(
  integrated: Mapping[str, Any],
  *,
  query_provenance: Mapping[str, Any],
) -> dict[str, Any]:
  signals = apply_relevance_ranking(list(integrated.get("signals", []) or []), query_provenance=query_provenance)
  grouped = group_signals_by_tier(signals)
  return {
    **dict(integrated),
    "signals": signals,
    "ranked_count": len(signals),
    "relevance_summary": {
      "tier_a": len(grouped[TIER_A]),
      "tier_b": len(grouped[TIER_B]),
      "tier_c": len(grouped[TIER_C]),
      "tier_d": len(grouped[TIER_D]),
    },
  }
