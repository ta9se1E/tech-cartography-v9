"""Tests for cross-theme core validation summary (Phase 24.4B)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.validation.core_validation_summary import (
  FREEZE_READY_WITH_DECLARED_LIMITATIONS,
  build_core_validation_summary,
  render_cross_theme_core_validation_summary_md,
  render_freeze_readiness_judgement_md,
  render_reviewer_response_notes_md,
  save_core_validation_summary_pack,
)
from tech_cartography.validation.seed_progress import save_seed_progress_report
from tech_cartography.validation.seed_progress import inspect_seed_progress_many
from tech_cartography.validation.theme_validation import save_user_manual_claims

LONG_CLAIMS = "【請求項1】" + ("PAN炭素繊維前駆体の表面欠陥制御に関する記載。" * 20)

SEEDS = ["JP2022090764A", "JP2023163084A", "JP2018084002A"]
THEME_ID = "pan_precursor_surface_internal_defects"
THEME_NAME = "PAN系炭素繊維前駆体の表面・内部欠陥制御"


def _setup_three_seeds(tmp_path: Path) -> None:
  for pub in SEEDS:
    save_user_manual_claims(
      publication_number=pub,
      claims_text=LONG_CLAIMS,
      output_dir=tmp_path,
    )
    skel_dir = tmp_path / "outputs" / "evidence_map_synthesis" / pub
    skel_dir.mkdir(parents=True)
    (skel_dir / "evidence_map_skeleton.json").write_text("{}", encoding="utf-8")


def test_build_summary_three_seeds_stage_pass_counts(tmp_path: Path) -> None:
  _setup_three_seeds(tmp_path)
  progress = inspect_seed_progress_many(SEEDS, tmp_path)
  save_seed_progress_report(
    progress,
    tmp_path / "outputs" / "validation" / "theme_validation",
    THEME_ID,
  )

  summary = build_core_validation_summary(
    project_root=tmp_path,
    theme_id=THEME_ID,
    theme_name=THEME_NAME,
    seed_publications=SEEDS,
  )

  assert summary.seed_count == 3
  assert summary.stage2_pass_count == 3
  assert summary.stage3_pass_count == 3
  assert set(summary.completed_seed_publications) == set(SEEDS)
  assert summary.incomplete_seed_publications == []
  assert summary.freeze_readiness == FREEZE_READY_WITH_DECLARED_LIMITATIONS
  assert summary.seed_progress_report_loaded is True


def test_save_pack_generates_all_files(tmp_path: Path) -> None:
  _setup_three_seeds(tmp_path)
  summary = build_core_validation_summary(
    project_root=tmp_path,
    theme_id=THEME_ID,
    theme_name=THEME_NAME,
    seed_publications=SEEDS,
  )
  out = tmp_path / "outputs" / "validation" / "core_validation"
  paths = save_core_validation_summary_pack(summary, out)

  assert paths["cross_theme_core_validation_summary_md"].exists()
  assert paths["cross_theme_core_validation_summary_json"].exists()
  assert paths["freeze_readiness_judgement_md"].exists()
  assert paths["reviewer_response_notes_md"].exists()
  assert paths["readme_patch_notes_md"].exists()
  assert paths["demo_script_patch_notes_md"].exists()
  assert paths["known_limitations_patch_notes_md"].exists()

  md = paths["cross_theme_core_validation_summary_md"].read_text(encoding="utf-8")
  assert THEME_NAME in md
  assert "Stage 4" in md or "未検証" in md
  assert "skeleton" in md.lower() or "最終 Evidence Map" in md
  assert "OpenAlex" in md or "外部API" in md
  assert "FTO" in md or "法的判断" in md
  assert "Manual Claims" in md

  data = json.loads(paths["cross_theme_core_validation_summary_json"].read_text(encoding="utf-8"))
  assert data["freeze_readiness"] == FREEZE_READY_WITH_DECLARED_LIMITATIONS
  assert len(data["unverified_scope"]) >= 5


def test_reviewer_response_notes_content(tmp_path: Path) -> None:
  _setup_three_seeds(tmp_path)
  summary = build_core_validation_summary(
    project_root=tmp_path,
    theme_id=THEME_ID,
    theme_name=THEME_NAME,
    seed_publications=SEEDS,
  )
  notes = render_reviewer_response_notes_md(summary)
  assert "Link Candidate" in notes
  assert "Phase23.4.1" in notes
  assert "再現性" in notes or "1件" in notes
  assert "SMTP" in notes or "scheduler" in notes
  assert FREEZE_READY_WITH_DECLARED_LIMITATIONS in notes


def test_freeze_judgement_and_unverified_scope(tmp_path: Path) -> None:
  _setup_three_seeds(tmp_path)
  summary = build_core_validation_summary(
    project_root=tmp_path,
    theme_id=THEME_ID,
    theme_name=THEME_NAME,
    seed_publications=SEEDS,
  )
  judgement = render_freeze_readiness_judgement_md(summary)
  main_md = render_cross_theme_core_validation_summary_md(summary)

  assert FREEZE_READY_WITH_DECLARED_LIMITATIONS in judgement
  assert "US-12565719-B2" in judgement
  assert "paper_candidates" in main_md or "論文候補" in main_md
  assert "web_signal" in main_md or "Webシグナル" in main_md
  for stage in summary.unverified_scope:
    assert stage in main_md or "未検証" in main_md


def test_incomplete_seed_not_freeze_ready(tmp_path: Path) -> None:
  save_user_manual_claims(
    publication_number="JP2022090764A",
    claims_text=LONG_CLAIMS,
    output_dir=tmp_path,
  )
  summary = build_core_validation_summary(
    project_root=tmp_path,
    theme_id=THEME_ID,
    theme_name=THEME_NAME,
    seed_publications=SEEDS,
  )
  assert summary.stage2_pass_count == 1
  assert summary.stage3_pass_count == 0
  assert summary.freeze_readiness == "not_ready_pending_seed_validation"
  assert len(summary.incomplete_seed_publications) == 3
  assert summary.completed_seed_publications == []
