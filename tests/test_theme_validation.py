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
  build_theme_search_queries,
  create_manual_claims_template,
  parse_keyword_text,
  render_theme_validation_markdown,
  run_existing_outputs_validation,
  run_theme_patent_search,
  run_theme_validation_dry_run,
  run_theme_validation_smoke,
  save_theme_validation_result,
  save_user_manual_claims,
  THEME_VALIDATION_SAFETY_MESSAGES,
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
    material_or_process_keywords=[],
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
    material_or_process_keywords=[],
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
    material_or_process_keywords=[],
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


def test_parse_keyword_text_comma_and_newline() -> None:
  assert parse_keyword_text("a, b\nc") == ["a", "b", "c"]
  assert parse_keyword_text("") == []


def test_build_theme_search_queries() -> None:
  case = ThemeValidationCase(
    theme_id="film",
    theme_name="Polymer film",
    description="",
    core_keywords=["polymer film", "heat treatment"],
    application_keywords=["battery separator"],
    material_or_process_keywords=["crystallization"],
    exclude_keywords=["medical"],
    seed_publication_numbers=[],
    validation_goal="ui",
  )
  queries = build_theme_search_queries(case)
  assert queries
  assert any("polymer film" in q for q in queries)


def test_dry_run_does_not_call_external_api() -> None:
  case = ThemeValidationCase(
    theme_id="dry",
    theme_name="Dry",
    description="",
    core_keywords=["alpha"],
    application_keywords=[],
    material_or_process_keywords=[],
    exclude_keywords=[],
    seed_publication_numbers=[],
    validation_goal="",
  )
  result = run_theme_validation_dry_run(case)
  assert result.mode == "dry_run"
  assert result.stages[0].status == "pass"
  assert result.stages[1].status == "pass"
  assert any("外部API未実行" in w for w in result.warnings)


def test_existing_outputs_validation_detects_artifacts(tmp_path: Path) -> None:
  pub = "US-9999999-A1"
  ev = tmp_path / "outputs" / "evidence_map_synthesis" / pub
  ev.mkdir(parents=True)
  (ev / "evidence_map_synthesis.json").write_text("{}", encoding="utf-8")
  manual = tmp_path / "outputs" / "manual_fulltext_inputs"
  manual.mkdir(parents=True)
  (manual / f"{pub}.json").write_text(
    json.dumps({"claims_text": "independent claim text " * 20}),
    encoding="utf-8",
  )

  case = ThemeValidationCase(
    theme_id="existing",
    theme_name="Existing",
    description="",
    core_keywords=["kw"],
    application_keywords=[],
    material_or_process_keywords=[],
    exclude_keywords=[],
    seed_publication_numbers=[pub],
    validation_goal="",
  )
  result = run_existing_outputs_validation(case, tmp_path)
  statuses = {stage.stage: stage.status for stage in result.stages}
  assert statuses["evidence_map_available_or_buildable"] == "pass"
  assert statuses["fulltext_or_manual_claims_available"] == "pass"
  assert statuses["digest_available"] == "output_missing"


def test_evidence_map_stage_passes_for_skeleton_only(tmp_path: Path) -> None:
  pub = "JP2022090764A"
  save_user_manual_claims(
    publication_number=pub,
    claims_text="【請求項1】" + ("PAN炭素繊維前駆体の乾燥熱履歴に関する記載。" * 20),
    output_dir=tmp_path,
  )
  skel_dir = tmp_path / "outputs" / "evidence_map_synthesis" / pub
  skel_dir.mkdir(parents=True)
  (skel_dir / "evidence_map_skeleton.json").write_text('{"publication_number":"JP2022090764A"}', encoding="utf-8")

  case = ThemeValidationCase(
    theme_id="pan_precursor_surface_internal_defects",
    theme_name="PAN",
    description="",
    core_keywords=["PAN"],
    application_keywords=[],
    material_or_process_keywords=[],
    exclude_keywords=[],
    seed_publication_numbers=[pub],
    validation_goal="",
  )
  result = run_existing_outputs_validation(case, tmp_path)
  stage = next(s for s in result.stages if s.stage == "evidence_map_available_or_buildable")
  assert stage.status == "pass"
  assert "skeleton" in stage.reason.lower()


def test_existing_outputs_missing_manual_input_required(tmp_path: Path) -> None:
  pub = "US-8888888-A1"
  case = ThemeValidationCase(
    theme_id="missing",
    theme_name="Missing",
    description="",
    core_keywords=["kw"],
    application_keywords=[],
    material_or_process_keywords=[],
    exclude_keywords=[],
    seed_publication_numbers=[pub],
    validation_goal="",
  )
  result = run_existing_outputs_validation(case, tmp_path)
  manual_stage = next(s for s in result.stages if s.stage == "fulltext_or_manual_claims_available")
  assert manual_stage.status == "manual_input_required"


def test_create_manual_claims_template(tmp_path: Path) -> None:
  out = tmp_path / "outputs" / "validation" / "theme_validation" / "theme_a"
  path = create_manual_claims_template("US-1-A1", out, project_root=tmp_path)
  assert path.exists()
  assert (tmp_path / "outputs" / "manual_fulltext_inputs" / "US-1-A1.template.json").exists()


def test_save_theme_validation_result_outputs(tmp_path: Path) -> None:
  case = ThemeValidationCase(
    theme_id="save_me",
    theme_name="Save",
    description="",
    core_keywords=["x"],
    application_keywords=[],
    material_or_process_keywords=[],
    exclude_keywords=[],
    seed_publication_numbers=[],
    validation_goal="",
  )
  result = run_theme_validation_dry_run(case)
  paths = save_theme_validation_result(result, tmp_path / "outputs" / "validation" / "theme_validation")
  assert paths["theme_validation_report_md"].exists()
  assert paths["theme_validation_result_json"].exists()
  assert paths["theme_validation_matrix_csv"].exists()
  md = paths["theme_validation_report_md"].read_text(encoding="utf-8")
  assert "FTO" in md
  assert any(msg in md for msg in THEME_VALIDATION_SAFETY_MESSAGES)


def test_external_search_not_configured_without_bigquery(tmp_path: Path, monkeypatch) -> None:
  monkeypatch.setattr(
    "tech_cartography.retrieval.bigquery_env.resolve_project_id",
    lambda *args, **kwargs: {"project_id": "", "source": "none", "error": "no project"},
  )
  monkeypatch.setattr(
    "tech_cartography.retrieval.bigquery_env.check_bigquery_environment",
    lambda *args, **kwargs: {"overall_status": "error"},
  )
  case = ThemeValidationCase(
    theme_id="ext",
    theme_name="Ext",
    description="",
    core_keywords=["kw"],
    application_keywords=[],
    material_or_process_keywords=[],
    exclude_keywords=[],
    seed_publication_numbers=[],
    validation_goal="",
  )
  result = run_theme_patent_search(case, project_root=tmp_path, execute=True)
  patent_stage = next(s for s in result.stages if s.stage == "patent_candidates_available")
  assert patent_stage.status == "external_search_not_configured"


def test_render_theme_validation_markdown_includes_safety(tmp_path: Path) -> None:
  case = ThemeValidationCase(
    theme_id="md",
    theme_name="MD",
    description="",
    core_keywords=["a"],
    application_keywords=[],
    material_or_process_keywords=[],
    exclude_keywords=[],
    seed_publication_numbers=[],
    validation_goal="",
  )
  result = run_theme_validation_dry_run(case)
  md = render_theme_validation_markdown(result, project_root=tmp_path)
  assert "侵害" in md
  assert VALIDATION_CAUTION in md
