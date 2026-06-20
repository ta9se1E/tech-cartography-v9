"""Tests for Manual Claims UI editor and persistence (Phase 24.4A.2)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.ui import theme_validation_ui
from tech_cartography.validation.theme_validation import (
  MANUAL_CLAIMS_EDITOR_NOTICES,
  build_theme_id,
  has_manual_claims,
  render_theme_validation_markdown,
  run_existing_outputs_validation,
  save_user_manual_claims,
  summarize_manual_claims_status,
  ThemeValidationCase,
)

LONG_CLAIMS = "【請求項1】" + ("独立請求項の本文です。" * 30)


def test_save_manual_claims_with_text(tmp_path: Path) -> None:
  path, warnings = save_user_manual_claims(
    publication_number="JP2022090764A",
    claims_text=LONG_CLAIMS,
    output_dir=tmp_path,
  )
  assert path is not None
  assert path.exists()
  data = json.loads(path.read_text(encoding="utf-8"))
  assert data["input_type"] == "manual_claims"
  assert data["created_by"] == "streamlit_theme_validation_ui"
  assert data["verification_status"] == "user_provided_manual_claims"
  assert "not AI-generated" in data["caveat"]


def test_save_manual_claims_empty_text_skipped(tmp_path: Path) -> None:
  path, warnings = save_user_manual_claims(
    publication_number="JP2022090764A",
    claims_text="",
    output_dir=tmp_path,
  )
  assert path is None
  assert any("空" in warning for warning in warnings)


def test_save_manual_claims_short_text_warns(tmp_path: Path) -> None:
  path, warnings = save_user_manual_claims(
    publication_number="JP2022090764A",
    claims_text="short",
    output_dir=tmp_path,
  )
  assert path is not None
  assert any("短すぎる" in warning for warning in warnings)


def test_save_manual_claims_empty_publication_skipped(tmp_path: Path) -> None:
  path, warnings = save_user_manual_claims(
    publication_number="",
    claims_text=LONG_CLAIMS,
    output_dir=tmp_path,
  )
  assert path is None
  assert any("publication_number" in warning for warning in warnings)


def test_save_manual_claims_overwrite_protection(tmp_path: Path) -> None:
  save_user_manual_claims(
    publication_number="JP2022090764A",
    claims_text=LONG_CLAIMS,
    output_dir=tmp_path,
  )
  path, warnings = save_user_manual_claims(
    publication_number="JP2022090764A",
    claims_text=LONG_CLAIMS + " updated",
    output_dir=tmp_path,
    overwrite=False,
  )
  assert path is None
  assert any("上書き" in warning for warning in warnings)


def test_has_manual_claims_saved_template_missing(tmp_path: Path) -> None:
  assert has_manual_claims("JP1", tmp_path) == (False, "missing")

  template_dir = tmp_path / "outputs" / "manual_fulltext_inputs"
  template_dir.mkdir(parents=True)
  (template_dir / "JP2.template.json").write_text("{}", encoding="utf-8")
  assert has_manual_claims("JP2", tmp_path) == (False, "template_only")

  save_user_manual_claims(
    publication_number="JP3",
    claims_text=LONG_CLAIMS,
    output_dir=tmp_path,
  )
  assert has_manual_claims("JP3", tmp_path) == (True, "saved")

  empty_path = template_dir / "JP4.json"
  empty_path.write_text(json.dumps({"claims_text": ""}), encoding="utf-8")
  assert has_manual_claims("JP4", tmp_path) == (False, "empty")


def test_stage2_pass_after_manual_claims_save(tmp_path: Path) -> None:
  case = ThemeValidationCase(
    theme_id="pan_precursor_surface_internal_defects",
    theme_name="PAN前駆体",
    description="",
    core_keywords=["PAN", "defect"],
    application_keywords=[],
    material_or_process_keywords=[],
    exclude_keywords=[],
    seed_publication_numbers=["JP2022090764A"],
    validation_goal="",
  )
  before = run_existing_outputs_validation(case, tmp_path)
  before_stage = next(s for s in before.stages if s.stage == "fulltext_or_manual_claims_available")
  assert before_stage.status == "manual_input_required"

  save_user_manual_claims(
    publication_number="JP2022090764A",
    claims_text=LONG_CLAIMS,
    output_dir=tmp_path,
  )
  after = run_existing_outputs_validation(case, tmp_path)
  after_stage = next(s for s in after.stages if s.stage == "fulltext_or_manual_claims_available")
  assert after_stage.status == "pass"


def test_build_theme_id_not_single_short_token() -> None:
  theme_id = build_theme_id("PAN", core_keywords=["precursor", "defect"])
  assert theme_id != "pan"
  assert len(theme_id) >= 12


def test_build_theme_id_override_and_backward_compat() -> None:
  assert build_theme_id("PAN", theme_id_override="pan") == "pan"
  assert (
    build_theme_id(
      "PAN前駆体の表面内部欠陥",
      theme_id_override="pan_precursor_surface_internal_defects",
    )
    == "pan_precursor_surface_internal_defects"
  )


def test_report_includes_manual_claims_status(tmp_path: Path) -> None:
  case = ThemeValidationCase(
    theme_id="pan_precursor_surface_internal_defects",
    theme_name="PAN",
    description="",
    core_keywords=["PAN"],
    application_keywords=[],
    material_or_process_keywords=[],
    exclude_keywords=[],
    seed_publication_numbers=["JP2022090764A", "JP2023163084A"],
    validation_goal="",
  )
  save_user_manual_claims(
    publication_number="JP2022090764A",
    claims_text=LONG_CLAIMS,
    output_dir=tmp_path,
  )
  result = run_existing_outputs_validation(case, tmp_path)
  md = render_theme_validation_markdown(result, project_root=tmp_path)
  assert "## Manual Claims status" in md
  assert "JP2022090764A: manual claims saved" in md
  assert "JP2023163084A: missing" in md or "JP2023163084A: template only" in md
  assert "Evidence Map Builder" in md or "skeleton" in md


def test_ui_module_has_manual_claims_editor_copy() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "Manual Claims入力 / Manual Claims Editor" in text
  assert "claims_text" in text
  assert "Manual Claimsを保存する" in text
  assert "保存後に既存outputs検証を再実行する" in text
  assert "FTO" in "\n".join(MANUAL_CLAIMS_EDITOR_NOTICES)
  assert callable(theme_validation_ui.render_manual_claims_editor)
