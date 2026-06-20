"""Tests for JP seed end-to-end chain (Phase 24.4C)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from tech_cartography.evidence.openalex_limited_executor import execute_openalex_limited
from tech_cartography.validation.end_to_end_chain import (
  EndToEndChainConfig,
  build_paper_query_plan_from_skeleton,
  inspect_end_to_end_status,
  run_digest_step,
  run_link_candidate_step,
  run_paper_candidate_step,
  run_web_signal_candidate_step,
  save_end_to_end_chain_result,
)
from tech_cartography.validation.theme_validation import save_user_manual_claims

LONG_CLAIMS = "【請求項1】" + ("PAN炭素繊維前駆体の表面欠陥制御に関する記載。" * 20)
THEME_ID = "pan_precursor_surface_internal_defects"
THEME_NAME = "PAN系炭素繊維前駆体の表面・内部欠陥制御"
SEED = "JP2022090764A"


def _base_config(tmp_path: Path, **overrides) -> EndToEndChainConfig:
  defaults = dict(
    theme_id=THEME_ID,
    theme_name=THEME_NAME,
    publication_numbers=[SEED],
    output_root=str(tmp_path),
    max_papers=5,
    max_web_signals=10,
    run_openalex=False,
    run_tavily=False,
    dry_run=True,
    allow_external_api=False,
  )
  defaults.update(overrides)
  return EndToEndChainConfig(**defaults)


def _setup_stage3_seed(tmp_path: Path) -> None:
  save_user_manual_claims(publication_number=SEED, claims_text=LONG_CLAIMS, output_dir=tmp_path)
  ev_dir = tmp_path / "outputs" / "evidence_map_synthesis" / SEED
  ev_dir.mkdir(parents=True)
  (ev_dir / "evidence_map_skeleton.json").write_text(
    json.dumps({"query_plan": [{"element_id": "el1", "must_have_terms": ["PAN"], "should_have_terms": ["炭素繊維"]}]}),
    encoding="utf-8",
  )
  (ev_dir / "query_plan.json").write_text(
    json.dumps([{"element_id": "el1", "must_have_terms": ["PAN"], "should_have_terms": ["炭素繊維前駆体"]}]),
    encoding="utf-8",
  )
  with (ev_dir / "claim_elements.csv").open("w", encoding="utf-8", newline="") as handle:
    handle.write("element_id,publication_number,claim_number,element_text,keywords,process_terms,material_terms,property_terms\n")
    handle.write(f"el1,{SEED},1,PAN前駆体,PAN|炭素繊維,紡糸原液,PAN,\n")


def test_end_to_end_chain_config_created(tmp_path: Path) -> None:
  config = _base_config(tmp_path)
  assert config.theme_id == THEME_ID
  assert config.allow_external_api is False


def test_stage23_seed_detected(tmp_path: Path) -> None:
  _setup_stage3_seed(tmp_path)
  result = inspect_end_to_end_status(_base_config(tmp_path))
  assert len(result.seed_statuses) == 1
  seed = result.seed_statuses[0]
  assert seed.stage2_manual_claims == "pass"
  assert seed.stage3_evidence_skeleton == "pass"
  assert seed.stage4_paper_candidates == "external_api_required"


def test_paper_query_plan_from_skeleton(tmp_path: Path) -> None:
  _setup_stage3_seed(tmp_path)
  plan = build_paper_query_plan_from_skeleton(SEED, tmp_path)
  assert plan["publication_number"] == SEED
  assert len(plan["openalex_query_candidates"]) >= 1
  status = run_paper_candidate_step(_base_config(tmp_path), SEED, query_plan_only=True)
  plan_path = tmp_path / "outputs" / "paper_candidates" / SEED / "paper_query_plan.json"
  assert plan_path.exists()
  assert status.stage4_paper_candidates == "query_plan_ready"


def test_allow_external_api_false_skips_openalex(tmp_path: Path) -> None:
  _setup_stage3_seed(tmp_path)
  with patch(
    "tech_cartography.validation.end_to_end_chain.execute_openalex_limited",
    wraps=execute_openalex_limited,
  ) as mock_exec:
    status = run_paper_candidate_step(_base_config(tmp_path), SEED, query_plan_only=False)
    mock_exec.assert_not_called()
  assert status.stage4_paper_candidates == "external_api_required"


def test_allow_external_api_false_skips_tavily(tmp_path: Path) -> None:
  _setup_stage3_seed(tmp_path)
  with patch("tech_cartography.validation.end_to_end_chain.run_tavily_web_signal_pipeline") as mock_tavily:
    status = run_web_signal_candidate_step(_base_config(tmp_path), SEED, query_plan_only=False)
    mock_tavily.assert_not_called()
  assert (tmp_path / "outputs" / "web_signals" / f"{THEME_ID}_{SEED}" / "web_signal_query_plan.json").exists()
  assert status.stage5_web_signals in {"external_api_required", "query_plan_ready"}


def test_stage6_blocked_when_paper_web_query_plan_only(tmp_path: Path) -> None:
  _setup_stage3_seed(tmp_path)
  run_paper_candidate_step(_base_config(tmp_path), SEED, query_plan_only=True)
  run_web_signal_candidate_step(_base_config(tmp_path), SEED, query_plan_only=True)
  status = run_link_candidate_step(_base_config(tmp_path), SEED)
  assert status.stage6_link_candidates == "blocked_missing_paper_or_web_signal"


def test_stage6_blocked_when_web_missing(tmp_path: Path) -> None:
  _setup_stage3_seed(tmp_path)
  pdir = tmp_path / "outputs" / "paper_candidates" / SEED
  pdir.mkdir(parents=True)
  (pdir / "selected_evidence_papers.csv").write_text(
    "publication_number,title\nJP2022090764A,Test paper\n",
    encoding="utf-8",
  )
  status = run_link_candidate_step(_base_config(tmp_path), SEED)
  assert status.stage6_link_candidates == "web_signal_missing"


def test_link_score_distribution_when_data_present(tmp_path: Path) -> None:
  _setup_stage3_seed(tmp_path)
  pdir = tmp_path / "outputs" / "paper_candidates" / SEED
  pdir.mkdir(parents=True)
  (pdir / "selected_evidence_papers.csv").write_text(
    "publication_number,title,paper_title,keywords\n"
    f"{SEED},PAN precursor stabilization,Stabilization of PAN fibers,carbonization|precursor\n",
    encoding="utf-8",
  )
  wdir = tmp_path / "outputs" / "web_signals" / f"{THEME_ID}_{SEED}" / "review_pack"
  wdir.mkdir(parents=True)
  (wdir / "high_priority_web_signals.csv").write_text(
    "signal_id,title,url,domain,signal_type,priority,snippet\n"
    "sig1,NEDO carbon fiber project,https://nedo.go.jp/1,nedo.go.jp,national_project,high,PAN precursor R&D\n",
    encoding="utf-8",
  )
  status = run_link_candidate_step(_base_config(tmp_path), SEED)
  summary = tmp_path / "outputs" / "web_signal_links" / SEED / "patent_paper_web_signal_summary.md"
  assert summary.exists()
  text = summary.read_text(encoding="utf-8")
  assert "Score distribution" in text or status.stage6_link_candidates == "pass"


def test_digest_preview_saved(tmp_path: Path) -> None:
  _setup_stage3_seed(tmp_path)
  status = run_digest_step(_base_config(tmp_path), SEED)
  md = tmp_path / "outputs" / "delivery" / f"jp_seed_digest_{SEED}.md"
  assert md.exists()
  assert status.stage8_digest == "pass"
  assert "JP Seed Validation Digest" in md.read_text(encoding="utf-8")


def test_end_to_end_summary_md_generated(tmp_path: Path) -> None:
  _setup_stage3_seed(tmp_path)
  result = inspect_end_to_end_status(_base_config(tmp_path))
  out = tmp_path / "outputs" / "validation" / "end_to_end_chain" / THEME_ID
  paths = save_end_to_end_chain_result(result, out)
  assert paths["end_to_end_chain_summary_md"].exists()
  md = paths["end_to_end_chain_summary_md"].read_text(encoding="utf-8")
  assert "Stage4" in md or "Stage 4" in md
  assert "FTO" in md or "法的" in md or "注意" in md
  assert "未検証" in md or "external_api" in md or "external_api_required" in md
