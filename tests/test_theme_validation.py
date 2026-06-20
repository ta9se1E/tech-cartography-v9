"""Tests for theme validation smoke (Phase 24.4)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.validation.store import save_theme_validation_report
from tech_cartography.validation.theme_validation import (
  VALIDATION_CAUTION,
  ThemeValidationCase,
  find_theme_case,
  load_theme_validation_config,
  run_theme_validation_smoke,
)


def test_load_theme_config(tmp_path: Path) -> None:
  config = {
    "cases": [
      {
        "theme_id": "test_theme",
        "theme_name": "Test",
        "description": "desc",
        "core_keywords": ["PAN"],
        "application_keywords": [],
        "exclude_keywords": [],
        "seed_publication_numbers": ["US-12565719-B2"],
        "validation_goal": "smoke",
      },
    ],
  }
  path = tmp_path / "theme.json"
  path.write_text(json.dumps(config), encoding="utf-8")
  cases = load_theme_validation_config(path)
  assert len(cases) == 1
  assert find_theme_case(cases, "test_theme") is not None


def test_theme_smoke_dry_run_no_external_api(tmp_path: Path) -> None:
  pub = "US-12565719-B2"
  ev_dir = tmp_path / "outputs" / "evidence_map_synthesis" / pub
  ev_dir.mkdir(parents=True, exist_ok=True)
  (ev_dir / "evidence_map_synthesis.md").write_text("# map", encoding="utf-8")
  (ev_dir / "evidence_map_synthesis.json").write_text("{}", encoding="utf-8")
  manual = tmp_path / "inputs" / "manual"
  manual.mkdir(parents=True, exist_ok=True)
  (manual / f"{pub}_claims.txt").write_text("claim", encoding="utf-8")

  case = ThemeValidationCase(
    theme_id="pan_carbon_fiber_reference",
    theme_name="PAN carbon fiber reference",
    description="ref",
    core_keywords=["PAN"],
    application_keywords=[],
    exclude_keywords=[],
    seed_publication_numbers=[pub],
    validation_goal="reference",
  )
  result = run_theme_validation_smoke(
    project_root=tmp_path,
    theme_case=case,
    publication_number=pub,
    dry_run=True,
    no_external_api=True,
  )
  assert result.no_external_api is True
  assert result.stages[0].status == "pass"
  assert any(stage.stage_name == "evidence_map_available_or_buildable" for stage in result.stages)
  assert VALIDATION_CAUTION in result.caveat


def test_theme_smoke_seed_only(tmp_path: Path) -> None:
  case = ThemeValidationCase(
    theme_id="t1",
    theme_name="T1",
    description="",
    core_keywords=[],
    application_keywords=[],
    exclude_keywords=[],
    seed_publication_numbers=["US-12565719-B2"],
    validation_goal="seed",
  )
  result = run_theme_validation_smoke(
    project_root=tmp_path,
    theme_case=case,
    seed_only=True,
    no_external_api=True,
  )
  assert len(result.stages) <= 2


def test_save_theme_validation_report(tmp_path: Path) -> None:
  case = ThemeValidationCase(
    theme_id="report_theme",
    theme_name="Report",
    description="",
    core_keywords=[],
    application_keywords=[],
    exclude_keywords=[],
    seed_publication_numbers=[],
    validation_goal="",
  )
  result = run_theme_validation_smoke(
    project_root=tmp_path,
    theme_case=case,
    dry_run=True,
    no_external_api=True,
  )
  paths = save_theme_validation_report(result, tmp_path / "outputs" / "validation" / "theme_validation", project_root=tmp_path)
  assert paths["theme_report_md"].exists()
  assert paths["theme_report_json"].exists()
  assert paths["theme_matrix_csv"].exists()
  text = paths["theme_report_md"].read_text(encoding="utf-8")
  assert "FTO" not in text or "ではありません" in text
