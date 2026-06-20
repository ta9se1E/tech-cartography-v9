"""Tests for seed validation progress dashboard (Phase 24.4A.4)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.validation.seed_progress import (
  inspect_seed_progress,
  inspect_seed_progress_many,
  preferred_publication_for_evidence_map,
  preferred_publication_for_manual_claims,
  progress_to_dataframe,
  save_seed_progress_report,
  summarize_seed_progress_actions,
)
from tech_cartography.validation.theme_validation import save_user_manual_claims

LONG_CLAIMS = "【請求項1】" + ("PAN炭素繊維前駆体の乾燥熱履歴に関する記載。" * 20)


def test_manual_claims_saved_detected(tmp_path: Path) -> None:
  save_user_manual_claims(
    publication_number="JP2022090764A",
    claims_text=LONG_CLAIMS,
    output_dir=tmp_path,
  )
  progress = inspect_seed_progress("JP2022090764A", tmp_path)
  assert progress.manual_claims_status == "saved"
  assert progress.stage2_status == "pass"
  assert progress.stage3_status == "output_missing"
  assert "skeleton" in progress.next_action.lower()


def test_template_only_detected(tmp_path: Path) -> None:
  manual_dir = tmp_path / "outputs" / "manual_fulltext_inputs"
  manual_dir.mkdir(parents=True)
  (manual_dir / "JP2018084002A.template.json").write_text("{}", encoding="utf-8")
  progress = inspect_seed_progress("JP2018084002A", tmp_path)
  assert progress.manual_claims_status == "template_only"
  assert progress.stage2_status == "manual_input_required"


def test_skeleton_exists_stage3_pass(tmp_path: Path) -> None:
  save_user_manual_claims(
    publication_number="JP2022090764A",
    claims_text=LONG_CLAIMS,
    output_dir=tmp_path,
  )
  skel_dir = tmp_path / "outputs" / "evidence_map_synthesis" / "JP2022090764A"
  skel_dir.mkdir(parents=True)
  (skel_dir / "evidence_map_skeleton.json").write_text("{}", encoding="utf-8")
  progress = inspect_seed_progress("JP2022090764A", tmp_path)
  assert progress.evidence_map_status == "skeleton_exists"
  assert progress.stage3_status == "pass"
  assert "論文候補" in progress.next_action or "Webシグナル" in progress.next_action


def test_full_map_exists(tmp_path: Path) -> None:
  save_user_manual_claims(
    publication_number="JP2022090764A",
    claims_text=LONG_CLAIMS,
    output_dir=tmp_path,
  )
  ev_dir = tmp_path / "outputs" / "evidence_map_synthesis" / "JP2022090764A"
  ev_dir.mkdir(parents=True)
  (ev_dir / "evidence_map_synthesis.json").write_text("{}", encoding="utf-8")
  progress = inspect_seed_progress("JP2022090764A", tmp_path)
  assert progress.evidence_map_status == "full_map_exists"
  assert progress.stage3_status == "pass"
  assert "Full Evidence Map" in progress.next_action


def test_many_seeds_progress_dataframe(tmp_path: Path) -> None:
  save_user_manual_claims(
    publication_number="JP2022090764A",
    claims_text=LONG_CLAIMS,
    output_dir=tmp_path,
  )
  skel_dir = tmp_path / "outputs" / "evidence_map_synthesis" / "JP2022090764A"
  skel_dir.mkdir(parents=True)
  (skel_dir / "evidence_map_skeleton.json").write_text("{}", encoding="utf-8")

  items = inspect_seed_progress_many(
    ["JP2022090764A", "JP2023163084A", "JP2018084002A"],
    tmp_path,
  )
  assert len(items) == 3
  df = progress_to_dataframe(items)
  assert len(df) == 3
  by_pub = {row["publication_number"]: row for row in df.to_dict(orient="records")}
  assert by_pub["JP2022090764A"]["stage3_status"] == "pass"
  assert by_pub["JP2023163084A"]["manual_claims_status"] == "missing"


def test_next_action_summaries(tmp_path: Path) -> None:
  save_user_manual_claims(
    publication_number="JP2022090764A",
    claims_text=LONG_CLAIMS,
    output_dir=tmp_path,
  )
  skel_dir = tmp_path / "outputs" / "evidence_map_synthesis" / "JP2022090764A"
  skel_dir.mkdir(parents=True)
  (skel_dir / "evidence_map_skeleton.json").write_text("{}", encoding="utf-8")
  items = inspect_seed_progress_many(
    ["JP2022090764A", "JP2023163084A"],
    tmp_path,
  )
  pending, completed = summarize_seed_progress_actions(items)
  assert any("JP2023163084A" in row for row in pending)
  assert any("JP2022090764A" in row and "Stage 3" in row for row in completed)


def test_save_seed_progress_report(tmp_path: Path) -> None:
  items = inspect_seed_progress_many(["JP2023163084A"], tmp_path)
  paths = save_seed_progress_report(
    items,
    tmp_path / "outputs" / "validation" / "theme_validation",
    "pan_precursor_surface_internal_defects",
  )
  assert paths["seed_progress_report_md"].exists()
  assert paths["seed_progress_report_csv"].exists()
  assert paths["seed_progress_report_json"].exists()
  md = paths["seed_progress_report_md"].read_text(encoding="utf-8")
  assert "外部API" in md
  data = json.loads(paths["seed_progress_report_json"].read_text(encoding="utf-8"))
  assert data[0]["publication_number"] == "JP2023163084A"


def test_preferred_publication_helpers(tmp_path: Path) -> None:
  save_user_manual_claims(
    publication_number="JP2022090764A",
    claims_text=LONG_CLAIMS,
    output_dir=tmp_path,
  )
  items = inspect_seed_progress_many(
    ["JP2022090764A", "JP2023163084A"],
    tmp_path,
  )
  assert preferred_publication_for_manual_claims(items) == "JP2023163084A"
  assert preferred_publication_for_evidence_map(items) == "JP2022090764A"


def test_ui_has_seed_progress_section() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "Seed別 検証進捗 / Seed Validation Progress" in text
  assert "Seed進捗を更新する" in text
  assert "Seed進捗レポートを保存する" in text
  assert "OpenAlex" not in text or "実行しません" in text
