"""Tests for v9 patent retrieval execution and staging."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.services.v8_bigquery_safety import BigQuerySafetyConfig
from streamlit.testing.v1 import AppTest

from services_v9.patent_bigquery_query import (
  execute_patent_bigquery_retrieval,
  run_patent_bigquery_dry_run,
  save_patent_retrieval_artifacts,
)
from services_v9.search_plan import build_unified_search_plan

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUERY_SOURCE = (PROJECT_ROOT / "services_v9" / "patent_bigquery_query.py").read_text(encoding="utf-8")
TABS_SOURCE = (PROJECT_ROOT / "ui_v9" / "tabs.py").read_text(encoding="utf-8")


class _FakeJobConfig:
  def __init__(self, *, dry_run: bool, maximum_bytes_billed: int) -> None:
    self.dry_run = dry_run
    self.maximum_bytes_billed = maximum_bytes_billed


class _FakeDryRunJob:
  def __init__(self, total_bytes_processed: int = 100_000_000) -> None:
    self.total_bytes_processed = total_bytes_processed
    self.job_id = "fake-dry-run-job"
    self.cache_hit = False


class _FakeResult:
  def __init__(self, rows: list[dict], fail_after: int | None = None) -> None:
    self.rows = list(rows)
    self.fail_after = fail_after

  def __iter__(self):
    for index, row in enumerate(self.rows):
      if self.fail_after is not None and index >= self.fail_after:
        raise RuntimeError("partial failure during iteration")
      yield row


class _FakeExecuteJob:
  def __init__(
    self,
    rows: list[dict],
    fail_after: int | None = None,
    *,
    total_bytes_processed: int = 240_000_000,
    total_bytes_billed: int = 128_000_000,
    cache_hit: bool = False,
  ) -> None:
    self.job_id = "fake-execute-job"
    self._rows = rows
    self._fail_after = fail_after
    self.total_bytes_processed = total_bytes_processed
    self.total_bytes_billed = total_bytes_billed
    self.cache_hit = cache_hit

  def result(self):
    return _FakeResult(self._rows, fail_after=self._fail_after)


class _FakeClient:
  def __init__(self, *, dry_run_bytes: int = 100_000_000, execute_rows: list[dict] | None = None, fail_after: int | None = None) -> None:
    self.dry_run_bytes = dry_run_bytes
    self.execute_rows = execute_rows or []
    self.fail_after = fail_after
    self.last_job_config = None
    self.last_job_id = ""

  def query(self, sql: str, job_config=None, job_id=None):  # noqa: ANN001
    self.last_job_config = job_config
    self.last_job_id = str(job_id or "")
    if getattr(job_config, "dry_run", False):
      return _FakeDryRunJob(self.dry_run_bytes)
    return _FakeExecuteJob(self.execute_rows, fail_after=self.fail_after)


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


def _config() -> BigQuerySafetyConfig:
  return BigQuerySafetyConfig(
    enable_bigquery_run=True,
    show_bigquery_admin=True,
    bigquery_project_id="test-project",
    bigquery_location="US",
    bigquery_max_bytes_billed=500_000_000,
    bigquery_default_limit=1000,
    bigquery_dry_run_only=False,
    bigquery_allow_execute=True,
  )


def _preview_and_dry_run() -> tuple[dict, dict]:
  from services_v9.patent_bigquery_query import build_patent_bigquery_preview

  plan = build_unified_search_plan(_profile())
  preview = build_patent_bigquery_preview(plan, _profile(), config=_config())
  dry_run_result = run_patent_bigquery_dry_run(
    preview,
    client_factory=lambda project_id, location: _FakeClient(dry_run_bytes=120_000_000),
    job_config_builder=lambda payload, dry_run: _FakeJobConfig(
      dry_run=dry_run,
      maximum_bytes_billed=int(payload["maximum_bytes_billed"]),
    ),
    config=_config(),
  )
  return preview, dry_run_result


def test_execute_requires_approved_query() -> None:
  preview, dry_run_result = _preview_and_dry_run()
  result = execute_patent_bigquery_retrieval(preview, dry_run_result, approved=False, config=_config())
  assert result["provider_status"] == "not_approved"
  assert result["rows"] == []


def test_execute_requires_successful_dry_run() -> None:
  preview, dry_run_result = _preview_and_dry_run()
  dry_run_result["dry_run_status"] = "error"
  result = execute_patent_bigquery_retrieval(preview, dry_run_result, approved=True, config=_config())
  assert result["provider_status"] == "dry_run_required"


def test_execute_returns_staged_patent_candidates() -> None:
  preview, dry_run_result = _preview_and_dry_run()
  fake_rows = [
    {
      "publication_number": "US-2024-000001-A1",
      "application_number": "US-123",
      "family_id": "FAM-1",
      "country": "US",
      "publication_date": "20240101",
      "priority_date": "20230101",
      "title": "PAN precursor fiber",
      "abstract": "metadata only",
      "assignee": "TORAY",
      "inventor": "Inventor A",
      "cpc_codes": "D01F",
      "source_url": "https://example.com/1",
    }
  ]
  client = _FakeClient(execute_rows=fake_rows)
  result = execute_patent_bigquery_retrieval(
    preview,
    dry_run_result,
    approved=True,
    client_factory=lambda project_id, location: client,
    job_config_builder=lambda payload, dry_run: _FakeJobConfig(
      dry_run=dry_run,
      maximum_bytes_billed=int(payload["maximum_bytes_billed"]),
    ),
    config=_config(),
  )
  assert result["provider_status"] == "success"
  assert result["rows_retrieved"] == 1
  row = result["rows"][0]
  assert row["publication_number"] == "US2024000001A1"
  assert row["record_stage"] == "staged"
  assert row["retrieval_mode"] == "real"
  assert row["query_id"] == preview["request"]["query_id"]
  assert row["bigquery_job_id"] == "fake-execute-job"
  assert client.last_job_config.dry_run is False


def test_family_duplicate_candidates_are_identified() -> None:
  preview, dry_run_result = _preview_and_dry_run()
  fake_rows = [
    {"publication_number": "US-1", "family_id": "FAM-1", "title": "A", "abstract": "a"},
    {"publication_number": "US-2", "family_id": "FAM-1", "title": "B", "abstract": "b"},
  ]
  result = execute_patent_bigquery_retrieval(
    preview,
    dry_run_result,
    approved=True,
    client_factory=lambda project_id, location: _FakeClient(execute_rows=fake_rows),
    job_config_builder=lambda payload, dry_run: _FakeJobConfig(
      dry_run=dry_run,
      maximum_bytes_billed=int(payload["maximum_bytes_billed"]),
    ),
    config=_config(),
  )
  assert result["rows"][0]["family_duplicate_candidate"] is True
  assert result["rows"][1]["family_duplicate_group_size"] == 2


def test_partial_success_keeps_retrieved_rows() -> None:
  preview, dry_run_result = _preview_and_dry_run()
  fake_rows = [
    {"publication_number": "US-1", "family_id": "FAM-1", "title": "A", "abstract": "a"},
    {"publication_number": "US-2", "family_id": "FAM-2", "title": "B", "abstract": "b"},
  ]
  result = execute_patent_bigquery_retrieval(
    preview,
    dry_run_result,
    approved=True,
    client_factory=lambda project_id, location: _FakeClient(execute_rows=fake_rows, fail_after=1),
    job_config_builder=lambda payload, dry_run: _FakeJobConfig(
      dry_run=dry_run,
      maximum_bytes_billed=int(payload["maximum_bytes_billed"]),
    ),
    config=_config(),
  )
  assert result["provider_status"] == "partial_success"
  assert result["rows_retrieved"] == 1
  assert result["rows"][0]["publication_number"] == "US1"


def test_execute_records_bigquery_job_metadata_and_deterministic_job_id() -> None:
  preview, dry_run_result = _preview_and_dry_run()
  preview["request"]["weekly_run_id"] = "cloud_weekly_job_20260704_123000"
  fake_rows = [{"publication_number": "US-1", "family_id": "FAM-1", "title": "A", "abstract": "a"}]
  client = _FakeClient(execute_rows=fake_rows)
  result = execute_patent_bigquery_retrieval(
    preview,
    dry_run_result,
    approved=True,
    client_factory=lambda project_id, location: client,
    job_config_builder=lambda payload, dry_run: _FakeJobConfig(
      dry_run=dry_run,
      maximum_bytes_billed=int(payload["maximum_bytes_billed"]),
    ),
    config=_config(),
  )
  assert client.last_job_id.startswith("v9_pat_")
  assert result["bigquery_job_id"] == "fake-execute-job"
  assert result["total_bytes_processed"] == 240_000_000
  assert result["total_bytes_billed"] == 128_000_000
  assert result["cache_hit"] is False
  assert result["sql_fingerprint"]
  assert result["selected_columns"]
  assert result["log"]["total_bytes_processed"] == 240_000_000
  assert result["log"]["total_bytes_billed"] == 128_000_000
  assert result["log"]["result_count"] == 1


def test_artifacts_are_saved_for_retrieval(tmp_path: Path) -> None:
  preview, dry_run_result = _preview_and_dry_run()
  retrieval_result = {
    "retrieval_run_id": "patent_retrieval_test",
    "query_id": preview["request"]["query_id"],
    "provider_status": "success",
    "bigquery_job_id": "job-1",
    "rows_retrieved": 1,
    "rows": [
      {
        "publication_number": "US1",
        "family_id": "FAM-1",
        "family_duplicate_candidate": False,
        "family_duplicate_group_size": 1,
        "title": "A",
        "abstract": "a",
        "assignee": "TORAY",
        "inventor": "Inventor A",
        "publication_date": "20240101",
        "priority_date": "20230101",
        "country": "US",
        "cpc_codes": "D01F",
        "source_url": "https://example.com/1",
        "query_id": preview["request"]["query_id"],
        "retrieval_run_id": "patent_retrieval_test",
        "bigquery_job_id": "job-1",
        "provider_status": "success",
        "record_stage": "staged",
        "retrieval_mode": "real",
      }
    ],
    "error": None,
    "log": {"provider_status": "success"},
  }
  paths = save_patent_retrieval_artifacts(preview, dry_run_result, retrieval_result, base_dir=tmp_path / "v9_runs")
  assert paths["staged_json"].name == "patent_candidates_staged.json"
  assert paths["staged_csv"].name == "patent_candidates_staged.csv"
  assert paths["retrieval_log_json"].name == "patent_retrieval_log.json"
  payload = json.loads(paths["staged_json"].read_text(encoding="utf-8"))
  assert payload["provider_status"] == "success"


def test_ui_source_contains_approval_and_execute_labels() -> None:
  required_labels = ["このqueryを承認", "承認済み特許取得を実行", "provider status", "retrieval_run_id"]
  assert all(label in TABS_SOURCE for label in required_labels)


def test_ui_code_does_not_auto_execute_on_render() -> None:
  assert "btn_patent_bigquery_execute" in TABS_SOURCE
  assert "execute_patent_bigquery_retrieval(" in QUERY_SOURCE


def test_streamlit_testing_finds_approval_and_execute_buttons() -> None:
  at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
  at.run()
  assert any(button.label == "このqueryを承認" for button in at.button)
  assert any(button.label == "承認済み特許取得を実行" for button in at.button)
