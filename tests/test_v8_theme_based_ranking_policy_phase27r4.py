"""Tests for Phase27R.4 theme-based ranking policy."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.runtime.v8_large_candidate_schema import V8LargeCandidateRecord
from tech_cartography.services.v8_research_theme_defaults import load_research_theme_profile
from tech_cartography.services.v8_theme_based_ranking_policy import (
  analyze_candidate_theme_fit,
  build_theme_based_ranking_policy,
  build_top5_reading_guide,
  build_why_selected_narrative,
  enrich_top5_record_with_theme,
  select_top5_preserving_existing,
)

CASE_ID = "case_01_pan_graphitization"
CN_TOP5 = (
  "CN108286090A",
  "CN117987966A",
  "CN105401262A",
  "CN105506785B",
  "CN109402791B",
)


def _sample_rec(pub: str = "CN108286090A") -> V8LargeCandidateRecord:
  return V8LargeCandidateRecord(
    candidate_id=f"cid:{pub}",
    case_id=CASE_ID,
    publication_number=pub,
    title="PAN precursor carbonization graphitization tensile strength",
    abstract="polyacrylonitrile precursor stabilization oxidation carbonization process",
    assignee="Example Corp",
    year="2018",
    heuristic_score=12.5,
    matched_keywords=["pan", "carbonization"],
    positive_reasons=['include term "pan" matched'],
    stage_label="top5",
    rank=1,
  )


def test_theme_ranking_policy_weights() -> None:
  policy = build_theme_based_ranking_policy(CASE_ID)
  assert policy.theme_name
  assert len(policy.weights) >= 8
  components = {w.component for w in policy.weights}
  assert "theme_fit" in components
  assert "noise_penalty" in components


def test_analyze_candidate_theme_fit() -> None:
  theme = load_research_theme_profile(CASE_ID)
  rec = _sample_rec()
  fit = analyze_candidate_theme_fit(rec, theme)
  assert fit.theme_fit > 0 or fit.process_fit > 0
  assert fit.publication_number == "CN108286090A"


def test_why_selected_narrative_no_legal_language() -> None:
  theme = load_research_theme_profile(CASE_ID)
  rec = _sample_rec()
  fit = analyze_candidate_theme_fit(rec, theme)
  text = build_why_selected_narrative(rec, theme, fit)
  assert "Top5" in text or "読む" in text
  assert "読む優先度" in text
  assert "出願できます" not in text


def test_enrich_top5_record_preserves_score() -> None:
  theme = load_research_theme_profile(CASE_ID)
  rec = _sample_rec()
  before_score = rec.heuristic_score
  enriched = enrich_top5_record_with_theme(rec, theme)
  assert enriched.heuristic_score == before_score
  assert enriched.why_selected
  assert len(enriched.positive_reasons) >= 1


def test_select_top5_preserving_existing() -> None:
  scored = [
    _sample_rec("US1111111A"),
    _sample_rec("CN108286090A"),
    _sample_rec("CN117987966A"),
    _sample_rec("CN105401262A"),
    _sample_rec("CN105506785B"),
    _sample_rec("CN109402791B"),
  ]
  for i, r in enumerate(scored):
    r.heuristic_score = float(20 - i)
  selected = select_top5_preserving_existing(scored, pinned_publications=list(CN_TOP5), top5_n=5)
  pubs = [r.publication_number for r in selected]
  assert pubs == list(CN_TOP5)


def test_patent_shortlist_ui_phase27r4() -> None:
  text = Path("src/tech_cartography/ui/v8_patent_shortlist_ui.py").read_text(encoding="utf-8")
  assert "Generate Reading Priority" in text
  assert "Top5 Deep Dive カード" in text or "render_top5_deep_dive_cards" in text
  assert "なぜTop5に残ったか" in text or "render_why_top5_section" in text
  assert "Top20から落ちた候補" in text or "render_dropped_summary_section" in text
  assert "use_container_width" not in text


def test_reading_guide_fields() -> None:
  theme = load_research_theme_profile(CASE_ID)
  rec = _sample_rec()
  fit = analyze_candidate_theme_fit(rec, theme)
  guide = build_top5_reading_guide(rec, theme, fit)
  assert guide.claim_map_focus
  assert guide.evidence_map_focus
  assert guide.examples_focus
  assert "権利範囲評価ではありません" in guide.caution
