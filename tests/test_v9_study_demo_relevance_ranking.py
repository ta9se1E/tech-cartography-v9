"""Tests for study demo relevance tiering and ranking (Stage C3)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from services_v9.study_demo_config import STUDY_DEMO_BUCKET_DEFAULT
from services_v9.study_demo_search.export import RELEVANCE_EXPORT_FIELDS, build_export_bundle
from services_v9.study_demo_search.integration import integrate_search_results
from services_v9.study_demo_search.relevance_ranking import (
  TIER_A,
  TIER_B,
  TIER_C,
  TIER_D,
  _context_from_provenance,
  _score_signal,
  apply_relevance_ranking,
  enrich_integrated_signals,
  filter_ranked_signals,
  group_signals_by_tier,
)
from services_v9.study_demo_search.storage import build_search_result_from_artifacts

FIXTURE_PATH = ROOT / "tests/fixtures/study_demo_relevance_ranking_samples.json"
PAN_PROVENANCE = {
  "theme": "PAN系炭素繊維のサイジング剤",
  "exact_phrase": "carbon fiber sizing agent",
  "keywords_en": "carbon fiber sizing polyurethane",
  "exclude_keywords": "textile,bamboo",
}
PAN_CTX = _context_from_provenance(PAN_PROVENANCE)


def _fixture() -> tuple[list[dict], dict]:
  payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
  return list(payload["signals"]), dict(payload["query_provenance"])


def _signal(**overrides: object) -> dict:
  base = {
    "source_type": "patent",
    "title": "",
    "summary": "",
    "metadata": {},
  }
  base.update(overrides)
  return base


def test_carbon_fiber_and_sizing_in_title_is_tier_a() -> None:
  scored = _score_signal(
    _signal(title="Aqueous polyurethane sizing agent for carbon fiber tow"),
    PAN_CTX,
  )
  assert scored["relevance_tier"] == TIER_A


def test_exact_phrase_title_gets_strong_bonus() -> None:
  with_phrase = _score_signal(
    _signal(title="carbon fiber sizing agent for industrial tow"),
    PAN_CTX,
  )
  without_phrase = _score_signal(
    _signal(title="Carbon fiber tow processing agent"),
    PAN_CTX,
  )
  assert with_phrase["source_raw_score"] > without_phrase["source_raw_score"]
  assert "exact_phrase:title" in with_phrase["matched_core_terms"]


def test_abstract_match_weaker_than_title() -> None:
  title_hit = _score_signal(
    _signal(title="Carbon fiber sizing agent", summary=""),
    PAN_CTX,
  )
  abstract_hit = _score_signal(
    _signal(title="Composite materials", summary="carbon fiber sizing agent improves adhesion"),
    PAN_CTX,
  )
  assert title_hit["source_raw_score"] > abstract_hit["source_raw_score"]


def test_carbon_fiber_interface_is_tier_b() -> None:
  scored = _score_signal(
    _signal(title="Carbon fiber interfacial adhesion in epoxy composites", summary="impregnation study"),
    PAN_CTX,
  )
  assert scored["relevance_tier"] == TIER_B


def test_general_carbon_fiber_review_is_tier_c() -> None:
  scored = _score_signal(
    _signal(title="Carbon Fibers and Their Composite Materials", summary="general review handbook"),
    PAN_CTX,
  )
  assert scored["relevance_tier"] == TIER_C


def test_unrelated_textile_is_tier_d() -> None:
  scored = _score_signal(
    _signal(title="Antibacterial polyester fiber fabric", summary="textile manufacturing"),
    PAN_CTX,
  )
  assert scored["relevance_tier"] == TIER_D


def test_pan_terms_add_points() -> None:
  with_pan = _score_signal(
    _signal(title="PAN-based carbon fiber sizing agent", summary=""),
    PAN_CTX,
  )
  without_pan = _score_signal(
    _signal(title="Carbon fiber sizing agent", summary=""),
    PAN_CTX,
  )
  assert with_pan["source_raw_score"] >= without_pan["source_raw_score"]
  assert with_pan["target_material_match"] == "pan"


def test_pitch_terms_penalize_when_pan_target() -> None:
  scored = _score_signal(
    _signal(title="Asphalt-based carbon fiber sizing agent", summary=""),
    PAN_CTX,
  )
  assert scored["target_material_mismatch"] == "pitch/asphalt"
  assert scored.get("score_breakdown", {}).get("pitch_mismatch") == -12


def test_pitch_patent_not_removed() -> None:
  signals, provenance = _fixture()
  ranked = apply_relevance_ranking(signals, query_provenance=provenance)
  titles = [item["title"] for item in ranked]
  assert any("Asphalt-based carbon fiber sizing agent" in title for title in titles)


def test_exclude_term_in_title_strong_penalty() -> None:
  scored = _score_signal(
    _signal(title="Bamboo fiber textile fabric", summary=""),
    PAN_CTX,
  )
  assert scored["relevance_tier"] == TIER_D
  assert scored["source_raw_score"] <= 15


def test_cited_by_count_does_not_promote_unrelated_paper() -> None:
  low = _score_signal(
    _signal(
      source_type="paper",
      title="Carbon Fibers and Their Composite Materials",
      summary="general review",
      metadata={"cited_by_count": 9000},
    ),
    PAN_CTX,
  )
  direct = _score_signal(
    _signal(
      source_type="paper",
      title="Carbon fiber sizing agent performance",
      summary="carbon fiber sizing agent aqueous",
      metadata={"cited_by_count": 5},
    ),
    PAN_CTX,
  )
  assert direct["relevance_tier"] == TIER_A
  assert low["relevance_tier"] == TIER_C
  assert direct["source_raw_score"] > low["source_raw_score"]


def test_tavily_score_does_not_promote_unrelated_web() -> None:
  low = _score_signal(
    _signal(
      source_type="web_company",
      title="Antibacterial polyester fiber fabric",
      summary="textile",
      metadata={"score": 0.99},
    ),
    PAN_CTX,
  )
  assert low["relevance_tier"] == TIER_D


def test_source_normalization_per_source_type() -> None:
  signals = [
    _signal(source_type="patent", title="Carbon fiber sizing agent", summary=""),
    _signal(source_type="paper", title="Carbon fiber sizing agent", summary=""),
    _signal(source_type="web_company", title="Carbon fiber sizing agent", summary=""),
  ]
  ranked = apply_relevance_ranking(signals, query_provenance=PAN_PROVENANCE)
  for item in ranked:
    assert "source_normalized_score" in item
    assert "integrated_relevance_score" in item
  by_source = {item["source_type"]: item["source_normalized_score"] for item in ranked}
  assert len(by_source) == 3


def test_relevance_reason_generated() -> None:
  scored = _score_signal(
    _signal(title="Carbon fiber sizing agent with polyurethane", summary=""),
    PAN_CTX,
  )
  assert scored["relevance_reason"]
  assert "直接関連" in scored["relevance_reason"] or "補助" in scored["relevance_reason"]


def test_score_breakdown_matches_source_raw_score() -> None:
  scored = _score_signal(
    _signal(title="Bio-based aqueous polyurethane sizing agent for PAN-based carbon fiber", summary="drying"),
    PAN_CTX,
  )
  total = round(sum(float(v) for v in scored["score_breakdown"].values()), 4)
  assert abs(total - float(scored["source_raw_score"])) <= 0.02


def test_tier_group_separation() -> None:
  signals, provenance = _fixture()
  ranked = apply_relevance_ranking(signals, query_provenance=provenance)
  grouped = group_signals_by_tier(ranked)
  assert grouped[TIER_A]
  assert grouped[TIER_C]
  assert all(item["relevance_tier"] == TIER_A for item in grouped[TIER_A])


def test_tier_d_hidden_by_default_filter() -> None:
  signals, provenance = _fixture()
  ranked = apply_relevance_ranking(signals, query_provenance=provenance)
  visible = filter_ranked_signals(ranked, tiers=[TIER_A, TIER_B], min_score=35, include_background=False)
  assert all(item["relevance_tier"] in {TIER_A, TIER_B} for item in visible)


def test_export_includes_all_tiers() -> None:
  signals, provenance = _fixture()
  ranked = apply_relevance_ranking(signals, query_provenance=provenance)
  export = build_export_bundle(ranked, {}, {}, {})
  assert export["integrated_csv_all_tiers"]
  assert "relevance_tier" in export["integrated_csv_all_tiers"]


def test_filtered_export_differs_from_all() -> None:
  signals, provenance = _fixture()
  ranked = apply_relevance_ranking(signals, query_provenance=provenance)
  filtered = filter_ranked_signals(ranked, tiers=[TIER_A, TIER_B], min_score=0)
  export = build_export_bundle(ranked, {}, {}, {}, filtered_signals=filtered)
  assert export["filtered_results_json"] != export["all_results_json"]


def test_history_rebuild_does_not_call_external_apis() -> None:
  signals, provenance = _fixture()
  loaded = {
    "search_run_id": "fixture-run",
    "artifacts": {
      "integrated_signals.json": {"signals": signals},
      "search_request.json": provenance,
      "keyword_suggestions.json": {},
      "similar_patents.json": {},
      "usage_metrics.json": {},
      "search_status.json": {"status": "success"},
      "provider_status.json": {},
    },
  }
  with patch("services_v9.study_demo_search.patent_provider.run_study_demo_patent_execute") as patent_mock:
    with patch("services_v9.study_demo_search.paper_provider.run_study_demo_paper_execute") as paper_mock:
      with patch("services_v9.study_demo_search.web_provider.run_study_demo_web_execute") as web_mock:
        bundle = build_search_result_from_artifacts(loaded)
  assert bundle["integrated_signals"]["signals"]
  patent_mock.assert_not_called()
  paper_mock.assert_not_called()
  web_mock.assert_not_called()


def test_ranking_recompute_does_not_call_bigquery() -> None:
  with patch("services_v9.study_demo_search.patent_provider.run_study_demo_patent_execute") as patent_mock:
    enrich_integrated_signals({"signals": [_signal(title="Carbon fiber sizing agent", summary="")]}, query_provenance=PAN_PROVENANCE)
  patent_mock.assert_not_called()


def test_ranking_recompute_does_not_call_openalex() -> None:
  with patch("services_v9.study_demo_search.paper_provider.run_study_demo_paper_execute") as paper_mock:
    apply_relevance_ranking([_signal(title="Carbon fiber sizing agent", summary="")], query_provenance=PAN_PROVENANCE)
  paper_mock.assert_not_called()


def test_ranking_recompute_does_not_call_tavily() -> None:
  with patch("services_v9.study_demo_search.web_provider.run_study_demo_web_execute") as web_mock:
    apply_relevance_ranking([_signal(source_type="web_company", title="Carbon fiber sizing", summary="")], query_provenance=PAN_PROVENANCE)
  web_mock.assert_not_called()


def test_export_has_no_secret_fields() -> None:
  export = build_export_bundle([], {}, {}, {})
  blob = json.dumps(export).lower()
  assert "api_key" not in blob
  assert "password" not in blob


def test_check_script_plan_uses_fixture_only() -> None:
  completed = subprocess.run(
    [sys.executable, str(ROOT / "scripts/check_v9_study_demo_relevance_ranking.py"), "--plan"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
  )
  payload = json.loads(completed.stdout)
  assert payload["mode"] == "plan"
  assert payload["status"] == "ok"
  assert "fixture" in payload


def test_integrate_search_results_adds_relevance_fields() -> None:
  integrated = integrate_search_results(
    patent_rows=[{"publication_number": "JP-1", "title": "Carbon fiber sizing agent", "abstract": "aqueous polyurethane"}],
    paper_rows=[],
    web_rows=[],
    search_run_id="run-local",
    query_provenance=PAN_PROVENANCE,
  )
  signal = integrated["signals"][0]
  assert signal.get("relevance_tier") in {TIER_A, TIER_B, TIER_C, TIER_D}
  assert "relevance_summary" in integrated


def test_export_relevance_field_list_complete() -> None:
  assert "relevance_tier" in RELEVANCE_EXPORT_FIELDS
  assert "score_breakdown" in RELEVANCE_EXPORT_FIELDS


def test_ui_has_tier_sections() -> None:
  source = Path(ROOT / "ui_v9/study_demo_search_ui.py").read_text(encoding="utf-8")
  assert "Tier A" in source
  assert "Tier D" in source
  assert "minimum relevance score" in source


def test_demo_bucket_default_not_production() -> None:
  assert "study-demo" in STUDY_DEMO_BUCKET_DEFAULT


def test_existing_search_plan_still_works() -> None:
  from services_v9.study_demo_search import build_search_plan_preview, parse_search_request

  request = parse_search_request({"theme": "carbon fiber sizing", "keywords_en": "epoxy"})
  with patch.dict(
    "os.environ",
    {
      "V9_STUDY_DEMO_MODE": "true",
      "V9_STUDY_DEMO_SEARCH_ENABLED": "true",
      "V9_STUDY_DEMO_DISABLE_EXTERNAL_EXECUTION": "true",
    },
    clear=False,
  ):
    plan = build_search_plan_preview(
      request,
      patent_dry_run_runner=lambda *args, **kwargs: {
        "dry_run_status": "ok",
        "estimated_bytes": 1000,
        "would_be_blocked_by_max_bytes": False,
        "job_id": "dry",
        "total_bytes_processed": 1000,
      },
    )
  assert plan["status"] == "plan"
