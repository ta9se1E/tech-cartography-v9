"""Tests for final end-to-end validation summary (Phase 24.4D)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.validation.final_validation_summary import (
  FREEZE_READY_AFTER_CROSS_THEME_E2E,
  FREEZE_READY_WITH_DECLARED_E2E_LIMITATIONS,
  NOT_READY_FOR_FULL_E2E_FREEZE,
  build_final_validation_summary,
  render_final_end_to_end_validation_summary_md,
  save_final_validation_summary_pack,
)
from tech_cartography.validation.theme_validation import save_user_manual_claims

LONG_CLAIMS = "【請求項1】" + ("PAN炭素繊維前駆体の表面欠陥制御に関する記載。" * 20)
THEME_ID = "pan_precursor_surface_internal_defects"
THEME_NAME = "PAN系炭素繊維前駆体の表面・内部欠陥制御"
SEEDS = ["JP2022090764A", "JP2023163084A", "JP2018084002A"]


def _setup_full_e2e_seed(tmp_path: Path, pub: str, *, paper_data: bool = True, web_data: bool = True) -> None:
  save_user_manual_claims(publication_number=pub, claims_text=LONG_CLAIMS, output_dir=tmp_path)
  ev_dir = tmp_path / "outputs" / "evidence_map_synthesis" / pub
  ev_dir.mkdir(parents=True)
  (ev_dir / "evidence_map_skeleton.json").write_text("{}", encoding="utf-8")

  pdir = tmp_path / "outputs" / "paper_candidates" / pub
  pdir.mkdir(parents=True)
  if paper_data:
    (pdir / "selected_evidence_papers.csv").write_text("title\nTest\n", encoding="utf-8")
  else:
    (pdir / "paper_query_plan.json").write_text("{}", encoding="utf-8")

  wdir = tmp_path / "outputs" / "web_signals" / f"{THEME_ID}_{pub}"
  wdir.mkdir(parents=True)
  if web_data:
    (wdir / "web_signals.csv").write_text("title\nSig\n", encoding="utf-8")
  else:
    (wdir / "web_signal_query_plan.json").write_text("{}", encoding="utf-8")

  ldir = tmp_path / "outputs" / "web_signal_links" / pub
  ldir.mkdir(parents=True)
  (ldir / "web_signal_link_candidates.csv").write_text("link_score\n50\n", encoding="utf-8")
  (ldir / "patent_paper_web_signal_summary.md").write_text("# summary", encoding="utf-8")

  sdir = tmp_path / "outputs" / "strategic_watch_briefs" / pub
  sdir.mkdir(parents=True)
  (sdir / "strategic_watch_brief.md").write_text("# brief", encoding="utf-8")
  (sdir / "strategic_watch_brief.json").write_text("{}", encoding="utf-8")
  (sdir / "strategic_watch_items.csv").write_text("watch_id\nw1\n", encoding="utf-8")

  delivery = tmp_path / "outputs" / "delivery"
  delivery.mkdir(parents=True, exist_ok=True)
  (delivery / f"jp_seed_digest_{pub}.md").write_text("# JP Seed Validation Digest", encoding="utf-8")
  (delivery / f"jp_seed_digest_{pub}.html").write_text("<html></html>", encoding="utf-8")


def test_aggregate_three_seeds_stage_counts(tmp_path: Path) -> None:
  for pub in SEEDS:
    _setup_full_e2e_seed(tmp_path, pub)
  summary = build_final_validation_summary(
    project_root=tmp_path,
    theme_id=THEME_ID,
    theme_name=THEME_NAME,
    seed_publications=SEEDS,
  )
  assert summary.seed_count == 3
  assert summary.stage2_pass_count == 3
  assert summary.stage3_pass_count == 3
  assert summary.stage4_paper_count == 3
  assert summary.stage5_web_count == 3
  assert summary.stage6_link_count == 3
  assert summary.stage7_watch_count == 3
  assert summary.stage8_digest_count == 3
  assert summary.completed_end_to_end_count == 3


def test_freeze_ready_after_full_e2e(tmp_path: Path) -> None:
  for pub in SEEDS:
    _setup_full_e2e_seed(tmp_path, pub)
  summary = build_final_validation_summary(
    project_root=tmp_path,
    theme_id=THEME_ID,
    theme_name=THEME_NAME,
    seed_publications=SEEDS,
  )
  assert summary.freeze_readiness == FREEZE_READY_AFTER_CROSS_THEME_E2E


def test_query_plan_ready_distinction(tmp_path: Path) -> None:
  _setup_full_e2e_seed(tmp_path, SEEDS[0], paper_data=False, web_data=False)
  _setup_full_e2e_seed(tmp_path, SEEDS[1])
  _setup_full_e2e_seed(tmp_path, SEEDS[2])
  summary = build_final_validation_summary(
    project_root=tmp_path,
    theme_id=THEME_ID,
    theme_name=THEME_NAME,
    seed_publications=SEEDS,
  )
  assert summary.stage4_query_plan_count >= 1
  assert summary.stage5_query_plan_count >= 1
  first = next(s for s in summary.seed_statuses if s["publication_number"] == SEEDS[0])
  assert first["paper_data_type"] == "query_plan_only"
  assert first["web_data_type"] == "query_plan_only"
  assert summary.freeze_readiness == FREEZE_READY_WITH_DECLARED_E2E_LIMITATIONS


def test_not_ready_when_stage6_missing(tmp_path: Path) -> None:
  pub = SEEDS[0]
  save_user_manual_claims(publication_number=pub, claims_text=LONG_CLAIMS, output_dir=tmp_path)
  ev_dir = tmp_path / "outputs" / "evidence_map_synthesis" / pub
  ev_dir.mkdir(parents=True)
  (ev_dir / "evidence_map_skeleton.json").write_text("{}", encoding="utf-8")
  pdir = tmp_path / "outputs" / "paper_candidates" / pub
  pdir.mkdir(parents=True)
  (pdir / "paper_query_plan.json").write_text("{}", encoding="utf-8")
  summary = build_final_validation_summary(
    project_root=tmp_path,
    theme_id=THEME_ID,
    theme_name=THEME_NAME,
    seed_publications=SEEDS,
  )
  assert summary.freeze_readiness == NOT_READY_FOR_FULL_E2E_FREEZE


def test_save_pack_generates_files(tmp_path: Path) -> None:
  for pub in SEEDS:
    _setup_full_e2e_seed(tmp_path, pub)
  summary = build_final_validation_summary(
    project_root=tmp_path,
    theme_id=THEME_ID,
    theme_name=THEME_NAME,
    seed_publications=SEEDS,
  )
  out = tmp_path / "outputs" / "validation" / "final_validation"
  paths = save_final_validation_summary_pack(summary, out)
  assert paths["final_end_to_end_validation_summary_md"].exists()
  assert paths["final_end_to_end_validation_summary_json"].exists()
  assert paths["seed_end_to_end_status_csv"].exists()
  assert paths["freeze_readiness_final_md"].exists()
  assert paths["reviewer_response_final_md"].exists()

  md = paths["final_end_to_end_validation_summary_md"].read_text(encoding="utf-8")
  assert "query_plan_ready" in md or "query_plan" in md
  assert "supporting evidence candidate" in md or "証明ではない" in md
  assert "signal candidate" in md or "確認候補" in md
  assert "preview" in md.lower() or "preview only" in md
  assert "FTO" in md or "法的判断" in md

  data = json.loads(paths["final_end_to_end_validation_summary_json"].read_text(encoding="utf-8"))
  assert data["freeze_readiness"] in {
    FREEZE_READY_AFTER_CROSS_THEME_E2E,
    FREEZE_READY_WITH_DECLARED_E2E_LIMITATIONS,
  }


def test_summary_md_includes_stage_table(tmp_path: Path) -> None:
  _setup_full_e2e_seed(tmp_path, SEEDS[0])
  summary = build_final_validation_summary(
    project_root=tmp_path,
    theme_id=THEME_ID,
    theme_name=THEME_NAME,
    seed_publications=[SEEDS[0]],
  )
  md = render_final_end_to_end_validation_summary_md(summary)
  assert "Stage 2" in md
  assert "Stage 8" in md
  assert SEEDS[0] in md
