"""Tests for v9 patent BigQuery SQL preview and dry-run."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.services.v8_bigquery_safety import BigQuerySafetyConfig
from streamlit.testing.v1 import AppTest

from services_v9.patent_bigquery_query import (
  build_patent_bigquery_preview,
  build_patent_bigquery_sql,
  run_patent_bigquery_dry_run,
  save_patent_dry_run_artifacts,
  validate_patent_bigquery_request,
)
from services_v9.search_plan import build_unified_search_plan

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUERY_SOURCE = (PROJECT_ROOT / "services_v9" / "patent_bigquery_query.py").read_text(encoding="utf-8")
TABS_SOURCE = (PROJECT_ROOT / "ui_v9" / "tabs.py").read_text(encoding="utf-8")


class _FakeJobConfig:
  def __init__(self, *, dry_run: bool, maximum_bytes_billed: int) -> None:
    self.dry_run = dry_run
    self.maximum_bytes_billed = maximum_bytes_billed


class _FakeJob:
  def __init__(self, total_bytes_processed: int = 123_456_789) -> None:
    self.total_bytes_processed = total_bytes_processed
    self.job_id = "fake-dry-run-job"


class _FakeClient:
  def __init__(self, total_bytes_processed: int = 123_456_789) -> None:
    self.total_bytes_processed = total_bytes_processed
    self.last_sql = ""
    self.last_job_config = None

  def query(self, sql: str, job_config=None):  # noqa: ANN001
    self.last_sql = sql
    self.last_job_config = job_config
    return _FakeJob(self.total_bytes_processed)


def _profile() -> dict:
  return {
    "schema_version": "v9.2",
    "theme_name": "PAN系炭素繊維前駆体の欠陥制御",
    "theme_description": "前駆体の表面欠陥と内部ボイドを監視する",
    "keywords": {
      "core_en": ["PAN carbon fiber precursor", "surface defect"],
      "core_ja": ["PAN系炭素繊維前駆体", "表面欠陥"],
      "application_en": ["CFRP"],
      "application_ja": ["複合材補強"],
      "material_process_en": ["coagulation bath"],
      "material_process_ja": ["凝固浴"],
      "exclude_en": ["graphene"],
      "exclude_ja": ["汎用ニュース"],
    },
    "seed_publications": ["JP2022090764A"],
    "candidate_publications": ["JP2018141251A"],
    "target_companies": ["東レ", "Mitsubishi Chemical"],
    "countries": ["JP", "US"],
    "source_types": ["patent", "paper", "web", "company"],
    "cadence": "weekly",
    "priority_rules": [],
    "notes": "",
  }


def _safety_config(max_bytes: int = 500_000_000) -> BigQuerySafetyConfig:
  return BigQuerySafetyConfig(
    enable_bigquery_run=True,
    show_bigquery_admin=True,
    bigquery_project_id="test-project",
    bigquery_location="US",
    bigquery_max_bytes_billed=max_bytes,
    bigquery_default_limit=1000,
    bigquery_dry_run_only=True,
    bigquery_allow_execute=False,
  )


def test_build_preview_selects_patent_query() -> None:
  plan = build_unified_search_plan(_profile())
  preview = build_patent_bigquery_preview(plan, _profile(), config=_safety_config())
  assert preview["request"]["query_id"].startswith("patent_q")
  assert preview["request"]["search_source"] == "patent"


def test_preview_reflects_countries_keywords_companies_and_seed_publications() -> None:
  plan = build_unified_search_plan(_profile())
  preview = build_patent_bigquery_preview(plan, _profile(), config=_safety_config())
  request = preview["request"]
  assert request["country_codes"] == ["JP", "US"]
  assert request["include_terms"]
  assert "東レ" in request["target_companies"]
  assert "JP2022090764A" in request["seed_publications"]


def test_sql_uses_parameter_placeholders() -> None:
  plan = build_unified_search_plan(_profile())
  sql = build_patent_bigquery_preview(plan, _profile(), config=_safety_config())["sql"]
  assert "@include_terms" in sql
  assert "@country_codes" in sql
  assert "@seed_publications" in sql
  assert "LIMIT @max_results" in sql


def test_sql_avoids_contains_substr_with_dynamic_terms() -> None:
  plan = build_unified_search_plan(_profile())
  sql = build_patent_bigquery_preview(plan, _profile(), config=_safety_config())["sql"]
  assert "CONTAINS_SUBSTR" not in sql
  assert "STRPOS(" in sql


def test_sql_does_not_inline_malicious_keyword() -> None:
  profile = _profile()
  profile["keywords"]["core_en"] = ["PAN'; DROP TABLE x; --"]
  plan = build_unified_search_plan(profile)
  sql = build_patent_bigquery_preview(plan, profile, config=_safety_config())["sql"]
  assert "DROP TABLE" not in sql
  assert "@include_terms" in sql


def test_sql_stays_bibliographic_only() -> None:
  plan = build_unified_search_plan(_profile())
  sql = build_patent_bigquery_sql(build_patent_bigquery_preview(plan, _profile(), config=_safety_config())["request"])
  lowered = sql.lower()
  assert "claims" not in lowered
  assert "description" not in lowered
  assert "title_localized" in sql
  assert "abstract_localized" in sql


def test_validation_passes_for_valid_preview() -> None:
  plan = build_unified_search_plan(_profile())
  preview = build_patent_bigquery_preview(plan, _profile(), config=_safety_config())
  rows = validate_patent_bigquery_request(preview["request"], preview["sql"])
  assert rows == [{"status": "ok", "message": "validation passed"}]


def test_validation_warns_without_maximum_bytes_billed() -> None:
  plan = build_unified_search_plan(_profile())
  preview = build_patent_bigquery_preview(plan, _profile(), config=_safety_config(max_bytes=0))
  rows = validate_patent_bigquery_request(preview["request"], preview["sql"])
  assert any(row["status"] == "warning" for row in rows)


def test_dry_run_returns_estimates_without_execute() -> None:
  plan = build_unified_search_plan(_profile())
  preview = build_patent_bigquery_preview(plan, _profile(), config=_safety_config())
  fake_client = _FakeClient(total_bytes_processed=222_000_000)
  result = run_patent_bigquery_dry_run(
    preview,
    client_factory=lambda project_id, location: fake_client,
    job_config_builder=lambda payload, dry_run: _FakeJobConfig(
      dry_run=dry_run,
      maximum_bytes_billed=int(payload["maximum_bytes_billed"]),
    ),
    config=_safety_config(),
  )
  assert result["dry_run_status"] == "ok"
  assert result["estimated_bytes"] == 222_000_000
  assert result["execution_allowed"] is False
  assert result["execute_enabled"] is False
  assert fake_client.last_job_config.dry_run is True


def test_dry_run_blocks_when_estimate_exceeds_max_bytes() -> None:
  plan = build_unified_search_plan(_profile())
  preview = build_patent_bigquery_preview(plan, _profile(), config=_safety_config(max_bytes=100))
  fake_client = _FakeClient(total_bytes_processed=1_000)
  result = run_patent_bigquery_dry_run(
    preview,
    client_factory=lambda project_id, location: fake_client,
    job_config_builder=lambda payload, dry_run: _FakeJobConfig(
      dry_run=dry_run,
      maximum_bytes_billed=int(payload["maximum_bytes_billed"]),
    ),
    config=_safety_config(max_bytes=100),
  )
  assert result["would_be_blocked_by_max_bytes"] is True


def test_dry_run_rejected_when_bigquery_run_disabled() -> None:
  plan = build_unified_search_plan(_profile())
  preview = build_patent_bigquery_preview(plan, _profile(), config=_safety_config())
  disabled = BigQuerySafetyConfig(
    enable_bigquery_run=False,
    show_bigquery_admin=False,
    bigquery_project_id="test-project",
    bigquery_location="US",
    bigquery_max_bytes_billed=1000,
    bigquery_default_limit=1000,
    bigquery_dry_run_only=True,
    bigquery_allow_execute=False,
  )
  result = run_patent_bigquery_dry_run(preview, config=disabled)
  assert result["dry_run_status"] == "rejected"


def test_artifacts_are_saved_with_expected_names(tmp_path: Path) -> None:
  plan = build_unified_search_plan(_profile())
  preview = build_patent_bigquery_preview(plan, _profile(), config=_safety_config())
  dry_run_result = {
    "dry_run_status": "ok",
    "estimated_bytes": 100,
    "estimated_gb": 0.0,
    "estimated_cost_usd": 0.0,
    "maximum_bytes_billed": 1000,
    "would_be_blocked_by_max_bytes": False,
    "query_validation": [{"status": "ok", "message": "validation passed"}],
    "execute_enabled": False,
    "execution_allowed": False,
    "error": None,
  }
  paths = save_patent_dry_run_artifacts(preview, dry_run_result, base_dir=tmp_path / "v9_runs")
  assert paths["sql"].name == "patent_query.sql"
  assert paths["plan_json"].name == "patent_query_plan.json"
  assert paths["dry_run_json"].name == "patent_dry_run.json"
  assert paths["validation_csv"].name == "patent_query_validation.csv"
  payload = json.loads(paths["dry_run_json"].read_text(encoding="utf-8"))
  assert payload["dry_run_status"] == "ok"


def test_ui_source_contains_patent_bigquery_labels() -> None:
  required_labels = [
    "Patent BigQuery SQL Preview",
    "特許BigQuery dry-runを実行",
    "SQL Preview",
    "parameter preview",
    "query validation",
  ]
  assert all(label in TABS_SOURCE for label in required_labels)


def test_ui_source_keeps_dry_run_label_even_after_b2_extension() -> None:
  assert "特許BigQuery dry-runを実行" in TABS_SOURCE


def test_ui_code_does_not_call_external_apis_directly() -> None:
  banned_tokens = [
    "requests.get(",
    "httpx.get(",
    "WebSearch(",
    "CallMcpTool(",
  ]
  assert all(token not in QUERY_SOURCE for token in banned_tokens)


def test_streamlit_testing_finds_patent_bigquery_controls() -> None:
  at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
  at.run()
  assert any(button.label == "特許BigQuery dry-runを実行" for button in at.button)
  assert any(select.label == "特許query_id" for select in at.selectbox)
