"""Top5 reading priority UI helpers (Phase 27R.4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.runtime.v8_large_candidate_schema import V8LargeCandidateRecord
from tech_cartography.services.v8_large_candidate_import import load_large_candidates_csv
from tech_cartography.services.v8_research_theme_defaults import load_research_theme_profile
from tech_cartography.services.v8_theme_based_ranking_policy import (
  analyze_candidate_theme_fit,
  build_dropped_from_top5_summary,
  build_theme_based_ranking_policy,
  build_top5_reading_guide,
)


def _load_json(path: Path) -> dict[str, Any]:
  if path.exists():
    return json.loads(path.read_text(encoding="utf-8"))
  return {}


def render_scoring_policy_section(*, triage_engine: str) -> None:
  st.markdown("#### スコアリング方針")
  st.markdown(
    "- **patent_triage**: include_terms +2/term, target_companies +3, US +1, pub/title/abstract +1, exclude -5/term\n"
    "- **theme_based_reading_priority_v1**: 研究テーマの core / process / property キーワード一致で説明を強化\n"
    "- いずれも **読む優先度のみ**。FTO / 侵害 / 有効性判断ではありません。"
  )
  st.caption(f"triage_engine: {triage_engine}")


def render_ranking_policy_metrics(
  *,
  case_id: str,
  triage_engine: str,
  ranking_policy: str,
  manifest: dict[str, Any],
  project_root: Path,
) -> None:
  st.markdown("#### Ranking Policy / Triage engine")
  theme_policy = manifest.get("theme_ranking_policy") or build_theme_based_ranking_policy(
    case_id, triage_engine=triage_engine, project_root=project_root,
  ).to_dict()
  weights = theme_policy.get("weights") or []
  if weights:
    cols = st.columns(min(4, len(weights)))
    for i, w in enumerate(weights[:8]):
      label = w.get("label_ja") or w.get("component", "")
      weight_val = w.get("weight", 0)
      cols[i % len(cols)].metric(w.get("component", f"w{i}"), f"{weight_val:+.2f}" if weight_val < 0 else f"{weight_val:.2f}")
  else:
    st.caption("theme weights 未生成")
  with st.expander("Ranking Policy / Triage engine（詳細説明）", expanded=False):
    st.markdown(f"**Ranking Policy:** `{ranking_policy}`")
    st.markdown(f"**Triage engine:** `{triage_engine}`")
    st.markdown(f"**Theme:** {theme_policy.get('theme_name', '—')}")
    st.caption(theme_policy.get("theme_description", ""))
    for w in weights:
      st.caption(f"- {w.get('component')}: weight={w.get('weight')} — {w.get('label_ja', '')}")


def render_top5_deep_dive_cards(
  top5: list[V8LargeCandidateRecord],
  *,
  case_id: str,
  project_root: Path,
) -> None:
  if not top5:
    st.caption("Top5 未生成")
    return
  theme = load_research_theme_profile(case_id, project_root)
  st.markdown("#### Top5 Deep Dive カード")
  for rec in top5:
    fit = analyze_candidate_theme_fit(rec, theme)
    guide = build_top5_reading_guide(rec, theme, fit)
    with st.container(border=True):
      st.markdown(f"**#{rec.rank} {rec.publication_number}** — {(rec.title or '')[:100]}")
      c1, c2, c3 = st.columns(3)
      c1.metric("reading_priority_score", rec.heuristic_score)
      c2.metric("theme_fit", fit.theme_fit)
      c3.metric("process_fit", fit.process_fit)
      st.caption(f"{rec.organization or rec.assignee} / {rec.year}")
      st.markdown(f"**なぜ読むべきか:** {guide.why_read}")
      st.markdown(f"**研究テーマとの関係:** {guide.theme_relationship}")
      st.markdown("**注目すべき技術要素**")
      for el in guide.technical_elements:
        st.markdown(f"- {el}")
      st.markdown(f"**Claim Mapで確認:** {guide.claim_map_focus}")
      st.markdown(f"**Evidence Mapで確認:** {guide.evidence_map_focus}")
      st.markdown(f"**実施例で確認:** {guide.examples_focus}")
      st.caption(f"caution: {guide.caution}")


def render_why_top5_section(
  top5: list[V8LargeCandidateRecord],
  *,
  case_id: str,
  project_root: Path,
) -> None:
  if not top5:
    return
  theme = load_research_theme_profile(case_id, project_root)
  st.markdown("#### なぜTop5に残ったか")
  for rec in top5:
    fit = analyze_candidate_theme_fit(rec, theme)
    guide = build_top5_reading_guide(rec, theme, fit)
    with st.expander(f"{rec.publication_number} — {rec.title[:50] if rec.title else 'no title'}", expanded=False):
      st.markdown(guide.narrative)
      if guide.positive_reasons:
        st.markdown("**positive reasons**")
        for p in guide.positive_reasons:
          st.markdown(f"- {p}")
      if guide.negative_reasons:
        st.markdown("**negative / caution reasons**")
        for n in guide.negative_reasons:
          st.markdown(f"- {n}")
      if fit.matched_theme_keywords:
        st.markdown(f"**matched theme keywords:** {', '.join(fit.matched_theme_keywords[:6])}")
      if fit.matched_process_keywords:
        st.markdown(f"**matched process keywords:** {', '.join(fit.matched_process_keywords[:6])}")
      if fit.matched_property_keywords:
        st.markdown(f"**matched property keywords:** {', '.join(fit.matched_property_keywords[:6])}")
      st.markdown(f"**why selected over others:** {guide.why_selected_over_others}")
      st.markdown(f"**next reading question:** {guide.next_reading_question}")


def render_dropped_summary_section(
  top20: list[V8LargeCandidateRecord],
  top5: list[V8LargeCandidateRecord],
  *,
  case_id: str,
  project_root: Path,
  manifest: dict[str, Any],
) -> None:
  st.markdown("#### Top20から落ちた候補の要約")
  dropped_data = manifest.get("dropped_from_top5") or {}
  if not dropped_data and top20 and top5:
    theme = load_research_theme_profile(case_id, project_root)
    dropped_data = build_dropped_from_top5_summary(top20, top5, theme).to_dict()
  st.metric("dropped_count", dropped_data.get("dropped_count", max(0, len(top20) - len(top5))))
  cats = dropped_data.get("category_counts") or {}
  if cats:
    st.markdown("**主な落選理由カテゴリ**")
    for cat, count in cats.items():
      st.markdown(f"- {cat}: {count}")
  examples = dropped_data.get("representative_examples") or []
  if examples:
    st.markdown("**代表例（最大3件）**")
    for ex in examples[:3]:
      st.markdown(
        f"- **{ex.get('publication_number')}** (score={ex.get('heuristic_score')}): "
        f"{ex.get('drop_reason', ex.get('drop_category', ''))}"
      )
  elif top20 and top5:
    top5_ids = {r.candidate_id for r in top5}
    for rec in [r for r in top20 if r.candidate_id not in top5_ids][:3]:
      st.markdown(f"- **{rec.publication_number}** (score={rec.heuristic_score}): 読む優先度スコア順位")


def load_stage_records(latest: Path | None) -> tuple[list, list, list]:
  if not latest:
    return [], [], []
  top100 = load_large_candidates_csv(latest / "large_candidate_top100.csv")
  top20 = load_large_candidates_csv(latest / "large_candidate_top20.csv")
  top5 = load_large_candidates_csv(latest / "large_candidate_top5.csv")
  return top100, top20, top5
