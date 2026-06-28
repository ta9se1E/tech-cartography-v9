"""Theme-based ranking policy and Top5 reading guides (Phase 27R.4)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from tech_cartography.runtime.v8_large_candidate_schema import V8LargeCandidateRecord
from tech_cartography.runtime.v8_research_theme_schema import ResearchThemeProfile
from tech_cartography.runtime.v8_theme_based_ranking_policy_schema import (
  DroppedFromTop5Example,
  DroppedFromTop5Summary,
  ThemeBasedRankingPolicy,
  ThemeCandidateFitAnalysis,
  ThemeRankingWeight,
  Top5ReadingGuide,
)
from tech_cartography.services.v8_research_theme_defaults import load_research_theme_profile

if TYPE_CHECKING:
  pass

DEFAULT_THEME_WEIGHTS: tuple[tuple[str, float, str], ...] = (
  ("theme_fit", 0.30, "研究テーマとの近さ"),
  ("material_fit", 0.20, "材料（PAN / precursor / carbon fiber 等）との近さ"),
  ("process_fit", 0.25, "工程（stabilization / carbonization / graphitization 等）"),
  ("property_fit", 0.20, "物性・欠陥（tensile / modulus / void / fuzz 等）"),
  ("claim_relevance", 0.15, "title / abstract / claim 関連語"),
  ("assignee_signal", 0.10, "出願人・企業・大学の動向"),
  ("recency", 0.10, "公開年"),
  ("source_quality", 0.10, "書誌情報・URL の有無"),
  ("noise_penalty", -0.20, "除外語（CNT / graphene / nanofiber 等）"),
)

PROCESS_HINT_TERMS: tuple[str, ...] = (
  "stabilization", "oxidation", "carbonization", "graphitization", "drawing", "stretching",
  "drying", "coagulation", "spinning", "wet spinning", "dry-jet", "precursor", "heat treatment",
  "炭化", "黒鉛化", "酸化", "安定化", "延伸", "乾燥", "紡糸", "凝固",
)

PROPERTY_HINT_TERMS: tuple[str, ...] = (
  "tensile", "modulus", "strength", "quality", "defect", "void", "fuzz", "fusion", "porosity",
  "roughness", "物性", "強度", "弾性率", "欠陥", "ボイド", "毛羽",
)

MATERIAL_HINT_TERMS: tuple[str, ...] = (
  "pan", "polyacrylonitrile", "precursor", "acrylic", "carbon fiber", "carbon fibre",
  "前駆体", "アクリル", "炭素繊維",
)

DROP_CATEGORY_LABELS: dict[str, str] = {
  "theme_distance": "テーマとの距離",
  "application_mismatch": "用途違い",
  "material_mismatch": "材料違い",
  "process_insufficient": "工程記載不足",
  "noise_terms": "ノイズ語含有",
  "information_gap": "情報不足",
  "score_rank": "読む優先度スコア順位",
}


def _blob(rec: V8LargeCandidateRecord) -> str:
  return " ".join([
    rec.title, rec.abstract, rec.organization, rec.assignee, rec.publication_number,
  ]).lower()


def _match_terms(blob: str, terms: list[str], *, limit: int = 8) -> list[str]:
  matched: list[str] = []
  for term in terms:
    tl = term.lower().strip()
    if not tl:
      continue
    if tl in blob and term not in matched:
      matched.append(term)
    if len(matched) >= limit:
      break
  return matched


def _ratio(matched_count: int, pool_size: int) -> float:
  if pool_size <= 0:
    return 0.0
  return round(min(1.0, matched_count / max(3, pool_size * 0.15)), 3)


def build_default_theme_weights() -> list[ThemeRankingWeight]:
  return [
    ThemeRankingWeight(component=c, weight=w, label_ja=label)
    for c, w, label in DEFAULT_THEME_WEIGHTS
  ]


def build_theme_based_ranking_policy(
  case_id: str,
  *,
  triage_engine: str = "",
  project_root: Path | str | None = None,
) -> ThemeBasedRankingPolicy:
  theme = load_research_theme_profile(case_id, project_root)
  return ThemeBasedRankingPolicy(
    case_id=case_id,
    theme_name=theme.theme_name,
    theme_description=theme.theme_description,
    triage_engine=triage_engine,
    weights=build_default_theme_weights(),
  )


def _theme_keyword_pools(theme: ResearchThemeProfile) -> tuple[list[str], list[str], list[str], list[str]]:
  theme_terms = list(dict.fromkeys([
    *theme.core_keywords,
    *theme.application_keywords[:12],
  ]))
  material_terms = list(dict.fromkeys([
    *[_t for _t in theme.core_keywords if any(h in _t.lower() for h in MATERIAL_HINT_TERMS)],
    *MATERIAL_HINT_TERMS,
  ]))[:24]
  process_terms = list(dict.fromkeys([
    *theme.material_process_keywords,
    *PROCESS_HINT_TERMS,
  ]))[:32]
  property_terms = list(dict.fromkeys([
    *[_t for _t in theme.application_keywords if any(h in _t.lower() for h in PROPERTY_HINT_TERMS)],
    *PROPERTY_HINT_TERMS,
  ]))[:24]
  return theme_terms, material_terms, process_terms, property_terms


def analyze_candidate_theme_fit(
  rec: V8LargeCandidateRecord,
  theme: ResearchThemeProfile,
) -> ThemeCandidateFitAnalysis:
  blob = _blob(rec)
  theme_terms, material_terms, process_terms, property_terms = _theme_keyword_pools(theme)

  matched_theme = _match_terms(blob, theme_terms)
  matched_material = _match_terms(blob, material_terms)
  matched_process = _match_terms(blob, process_terms)
  matched_property = _match_terms(blob, property_terms)
  matched_exclude = _match_terms(blob, list(theme.exclude_keywords))

  claim_relevance = _match_terms(blob, theme_terms + material_terms + process_terms, limit=6)
  assignee_hit = 1.0 if (rec.assignee or rec.organization) else 0.0

  year_val = 0.0
  if rec.year:
    try:
      y = int(re.search(r"\d{4}", str(rec.year)).group())  # type: ignore[union-attr]
      if y >= 2015:
        year_val = min(1.0, (y - 2000) / 25.0)
      elif y >= 2000:
        year_val = 0.4
    except (AttributeError, TypeError, ValueError):
      year_val = 0.2

  source_quality = 0.0
  if rec.publication_number:
    source_quality += 0.35
  if rec.title:
    source_quality += 0.25
  if rec.abstract:
    source_quality += 0.25
  if rec.url or rec.source_url:
    source_quality += 0.15
  source_quality = min(1.0, source_quality)

  noise = min(1.0, len(matched_exclude) * 0.35) if matched_exclude else 0.0

  return ThemeCandidateFitAnalysis(
    candidate_id=rec.candidate_id,
    publication_number=rec.publication_number,
    theme_fit=_ratio(len(matched_theme), len(theme_terms)),
    material_fit=_ratio(len(matched_material), len(material_terms)),
    process_fit=_ratio(len(matched_process), len(process_terms)),
    property_fit=_ratio(len(matched_property), len(property_terms)),
    claim_relevance=_ratio(len(claim_relevance), 6),
    assignee_signal=assignee_hit,
    recency=year_val,
    source_quality=source_quality,
    noise_penalty=noise,
    matched_theme_keywords=matched_theme,
    matched_material_keywords=matched_material,
    matched_process_keywords=matched_process,
    matched_property_keywords=matched_property,
    matched_exclude_keywords=matched_exclude,
  )


def _infer_drop_category(rec: V8LargeCandidateRecord, fit: ThemeCandidateFitAnalysis) -> str:
  if fit.matched_exclude_keywords:
    return "noise_terms"
  if fit.theme_fit < 0.15 and fit.material_fit < 0.15:
    return "theme_distance"
  if fit.material_fit < 0.1:
    return "material_mismatch"
  if fit.process_fit < 0.1 and fit.property_fit < 0.1:
    return "process_insufficient"
  if not rec.abstract and not rec.title:
    return "information_gap"
  if fit.property_fit < 0.1 and "application" in rec.title.lower():
    return "application_mismatch"
  return "score_rank"


def _drop_reason_text(category: str, fit: ThemeCandidateFitAnalysis, rec: V8LargeCandidateRecord) -> str:
  label = DROP_CATEGORY_LABELS.get(category, category)
  if category == "noise_terms" and fit.matched_exclude_keywords:
    terms = ", ".join(fit.matched_exclude_keywords[:3])
    return f"{label}: 除外語 {terms} を含有"
  if category == "theme_distance":
    return f"{label}: テーマキーワード一致が Top5 より少ない（score={rec.heuristic_score}）"
  if category == "process_insufficient":
    return f"{label}: 工程・物性に関する記載が Top5 候補より薄い"
  if category == "information_gap":
    return f"{label}: title / abstract / 書誌情報が不足"
  return f"{label}: 読む優先度スコア {rec.heuristic_score} が Top5 閾値未満"


def build_why_selected_narrative(
  rec: V8LargeCandidateRecord,
  theme: ResearchThemeProfile,
  fit: ThemeCandidateFitAnalysis,
) -> str:
  parts: list[str] = []
  if fit.matched_process_keywords or fit.matched_material_keywords:
    proc = ", ".join(fit.matched_process_keywords[:3]) or "前駆体・工程関連語"
    mat = ", ".join(fit.matched_material_keywords[:2]) or "材料関連語"
    parts.append(
      f"この特許は、{mat} および {proc} に関する記載が研究テーマ「{theme.theme_name or theme.case_id}」に近いため Top5 に残りました。"
    )
  elif fit.matched_theme_keywords:
    terms = ", ".join(fit.matched_theme_keywords[:4])
    parts.append(f"研究テーマキーワード {terms} に一致したため Top5 に残りました。")
  else:
    parts.append(
      f"読む優先度スコア {rec.heuristic_score} により Top5 に残りました（テーマ: {theme.theme_name or case_id_fallback(theme)}）。"
    )
  parts.append(
    "次に読むべき箇所は、description / examples に記載された温度条件、延伸条件、物性値、比較例です。"
  )
  parts.append("スコアは読む優先度のみであり、法的価値・権利範囲評価ではありません。")
  return " ".join(parts)


def case_id_fallback(theme: ResearchThemeProfile) -> str:
  return theme.case_id


def build_top5_reading_guide(
  rec: V8LargeCandidateRecord,
  theme: ResearchThemeProfile,
  fit: ThemeCandidateFitAnalysis,
) -> Top5ReadingGuide:
  narrative = build_why_selected_narrative(rec, theme, fit)
  technical: list[str] = []
  for kw in fit.matched_process_keywords[:3]:
    technical.append(f"工程: {kw}")
  for kw in fit.matched_property_keywords[:2]:
    technical.append(f"物性・欠陥: {kw}")
  for kw in fit.matched_material_keywords[:2]:
    technical.append(f"材料: {kw}")
  if not technical:
    technical.append("title / abstract から読み取れる前駆体・工程・物性キーワード")

  positives = list(rec.positive_reasons)
  if fit.matched_theme_keywords:
    positives.append(f"theme_keywords: {', '.join(fit.matched_theme_keywords[:4])}")
  if fit.matched_process_keywords:
    positives.append(f"process_keywords: {', '.join(fit.matched_process_keywords[:4])}")
  if fit.matched_property_keywords:
    positives.append(f"property_keywords: {', '.join(fit.matched_property_keywords[:4])}")

  negatives = list(rec.negative_reasons)
  if fit.matched_exclude_keywords:
    negatives.append(f"noise_terms: {', '.join(fit.matched_exclude_keywords[:3])}")
  if not rec.abstract:
    negatives.append("abstract 未確認 — 原典確認が必要")

  return Top5ReadingGuide(
    publication_number=rec.publication_number,
    title=rec.title,
    why_read=narrative.split("。")[0] + "。" if narrative else rec.why_selected,
    theme_relationship=(
      f"テーマ「{theme.theme_name}」— "
      f"theme_fit={fit.theme_fit}, process_fit={fit.process_fit}, property_fit={fit.property_fit}"
    ),
    technical_elements=technical,
    claim_map_focus="請求項の材料组成・工程ステップ・物性限界を Claim Map で整理",
    evidence_map_focus="paper / web / company の裏取り候補と support_level を Evidence Map で確認",
    examples_focus="description / examples の温度・延伸・比較例・物性値を人手確認",
    positive_reasons=positives[:8],
    negative_reasons=negatives[:5],
    why_selected_over_others=(
      f"Top20 内で reading_priority_score={rec.heuristic_score}、"
      f"テーマ一致語 {len(fit.matched_theme_keywords)} / 工程一致語 {len(fit.matched_process_keywords)}"
    ),
    next_reading_question="実施例条件・物性値・比較例は description / examples に記載されているか？",
    narrative=narrative,
  )


def enrich_top5_record_with_theme(
  rec: V8LargeCandidateRecord,
  theme: ResearchThemeProfile,
) -> V8LargeCandidateRecord:
  """Enrich why_selected / reasons without changing heuristic_score or rank."""
  fit = analyze_candidate_theme_fit(rec, theme)
  guide = build_top5_reading_guide(rec, theme, fit)
  copy = V8LargeCandidateRecord.from_dict(rec.to_dict())
  copy.why_selected = guide.narrative
  copy.positive_reasons = guide.positive_reasons
  if guide.negative_reasons:
    copy.negative_reasons = list(dict.fromkeys([*copy.negative_reasons, *guide.negative_reasons]))
  copy.next_verification_action = guide.next_reading_question
  return copy


def build_dropped_from_top5_summary(
  top20: list[V8LargeCandidateRecord],
  top5: list[V8LargeCandidateRecord],
  theme: ResearchThemeProfile,
) -> DroppedFromTop5Summary:
  top5_ids = {r.candidate_id for r in top5}
  dropped = [r for r in top20 if r.candidate_id not in top5_ids]
  category_counts: dict[str, int] = {}
  examples: list[DroppedFromTop5Example] = []

  for rec in dropped:
    fit = analyze_candidate_theme_fit(rec, theme)
    cat = _infer_drop_category(rec, fit)
    category_counts[cat] = category_counts.get(cat, 0) + 1

  for rec in dropped[:3]:
    fit = analyze_candidate_theme_fit(rec, theme)
    cat = _infer_drop_category(rec, fit)
    examples.append(DroppedFromTop5Example(
      publication_number=rec.publication_number,
      title=(rec.title or "")[:80],
      heuristic_score=rec.heuristic_score,
      drop_category=DROP_CATEGORY_LABELS.get(cat, cat),
      drop_reason=_drop_reason_text(cat, fit, rec),
    ))

  lines = [f"Top20 から Top5 外れ: {len(dropped)} 件"]
  for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
    lines.append(f"- {DROP_CATEGORY_LABELS.get(cat, cat)}: {count}")

  return DroppedFromTop5Summary(
    dropped_count=len(dropped),
    category_counts={DROP_CATEGORY_LABELS.get(k, k): v for k, v in category_counts.items()},
    representative_examples=examples,
    summary_text="\n".join(lines),
  )


def select_top5_preserving_existing(
  scored: list[V8LargeCandidateRecord],
  *,
  pinned_publications: list[str],
  top5_n: int,
) -> list[V8LargeCandidateRecord]:
  """Keep existing Top5 publication order when regenerating explanations."""
  if not pinned_publications:
    return scored[:top5_n]
  by_pub: dict[str, V8LargeCandidateRecord] = {}
  for rec in scored:
    if rec.publication_number:
      by_pub[rec.publication_number.upper()] = rec
  selected: list[V8LargeCandidateRecord] = []
  used: set[str] = set()
  for pub in pinned_publications:
    rec = by_pub.get(pub.upper())
    if rec and rec.candidate_id not in used:
      selected.append(rec)
      used.add(rec.candidate_id)
  for rec in scored:
    if len(selected) >= top5_n:
      break
    if rec.candidate_id not in used:
      selected.append(rec)
      used.add(rec.candidate_id)
  return selected[:top5_n]
