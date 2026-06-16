"""Tests for BigQuery light retriever."""

from __future__ import annotations

from unittest.mock import patch

from tech_cartography.config import load_carbon_fiber_demo_profile
from tech_cartography.retrieval.bigquery_env import gb_to_bytes
from tech_cartography.retrieval.bigquery_light_retriever import (
  RetrievalConfig,
  dry_run_query,
  execute_query,
  run_multi_query_retrieval,
  run_query_plan,
)
from tech_cartography.strategy.query_plan import QueryPlan
from tech_cartography.strategy.search_strategy_builder import build_query_plans


class _FakeJob:
  def __init__(self, total_bytes_processed: int = 1024**3) -> None:
    self.total_bytes_processed = total_bytes_processed


class _FakeQueryJob:
  def __init__(self, rows: list[dict]) -> None:
    self._rows = rows

  def result(self) -> list[dict]:
    return self._rows


class _FakeClient:
  def __init__(self, rows: list[dict] | None = None, total_bytes: int = 1024**3) -> None:
    self.rows = rows or []
    self.total_bytes = total_bytes
    self.last_job_config = None

  def query(self, sql: str, job_config=None):  # noqa: ANN001
    self.last_job_config = job_config
    if job_config and getattr(job_config, "dry_run", False):
      return _FakeJob(self.total_bytes)
    return _FakeQueryJob(self.rows)


def _sample_plans() -> list[QueryPlan]:
  profile = load_carbon_fiber_demo_profile()
  return build_query_plans(profile)[:2]


def test_retrieval_config_defaults_are_safe() -> None:
  config = RetrievalConfig()
  assert config.dry_run is True
  assert config.execute is False


def test_dry_run_query_mock_returns_estimated_bytes() -> None:
  config = RetrievalConfig(project_id="test-project", dry_run=True, execute=False)
  fake_client = _FakeClient(total_bytes=gb_to_bytes(2))

  def factory(project_id: str) -> _FakeClient:
    assert project_id == "test-project"
    return fake_client

  with patch(
    "tech_cartography.retrieval.bigquery_light_retriever.resolve_project_id",
    return_value={"project_id": "test-project", "source": "explicit", "error": None},
  ):
    result = dry_run_query("SELECT 1", config, client_factory=factory)

  assert result["dry_run_status"] == "ok"
  assert result["estimated_bytes"] == gb_to_bytes(2)
  assert result["estimated_gb"] == 2.0


def test_execute_false_does_not_call_execute_query() -> None:
  config = RetrievalConfig(project_id="test-project", execute=False)
  plan = _sample_plans()[0]

  with patch(
    "tech_cartography.retrieval.bigquery_light_retriever.dry_run_query",
    return_value={
      "dry_run_status": "ok",
      "estimated_bytes": 1000,
      "estimated_gb": 0.0,
      "estimated_usd": 0.0,
      "would_be_blocked_by_max_bytes": False,
      "error": None,
    },
  ), patch(
    "tech_cartography.retrieval.bigquery_light_retriever.execute_query",
  ) as execute_mock:
    result = run_query_plan(plan, config)

  execute_mock.assert_not_called()
  assert result["execution_status"] == "skipped"
  assert result["record_count"] == 0


def test_execute_true_passes_maximum_bytes_billed() -> None:
  config = RetrievalConfig(
    project_id="test-project",
    dry_run=False,
    execute=True,
    maximum_bytes_billed_gb=10.0,
  )
  fake_client = _FakeClient(
    rows=[
      {
        "publication_number": "US-2024-000001",
        "title": "PAN carbon fiber carbonization",
        "abstract": "modulus aerospace composite",
        "assignee": "TORAY",
        "country": "US",
        "publication_date": "20240101",
        "url": "https://example.com",
        "cpc_codes": "D01F",
        "ipc_codes": "D01F",
      },
    ],
  )

  def factory(project_id: str) -> _FakeClient:
    return fake_client

  with patch(
    "tech_cartography.retrieval.bigquery_light_retriever.resolve_project_id",
    return_value={"project_id": "test-project", "source": "explicit", "error": None},
  ):
    rows = execute_query("SELECT 1", config, client_factory=factory)

  assert len(rows) == 1
  assert fake_client.last_job_config.maximum_bytes_billed == gb_to_bytes(10.0)


def test_run_multi_query_retrieval_processes_each_plan(tmp_path) -> None:
  plans = _sample_plans()
  config = RetrievalConfig(
    project_id="test-project",
    execute=False,
    output_dir=str(tmp_path),
    use_cache=False,
  )

  with patch(
    "tech_cartography.retrieval.bigquery_light_retriever.check_bigquery_environment",
    return_value={"ready": True, "project_id": "test-project", "checks": []},
  ), patch(
    "tech_cartography.retrieval.bigquery_light_retriever.run_query_plan",
    side_effect=lambda plan, cfg, **kwargs: {
      "intent_id": plan.intent_id,
      "purpose": plan.purpose,
      "sql": "SELECT 1",
      "dry_run_status": "ok",
      "estimated_bytes": 1000,
      "estimated_gb": 0.0,
      "estimated_usd": 0.0,
      "would_be_blocked_by_max_bytes": False,
      "execution_status": "skipped",
      "record_count": 0,
      "records": [],
      "output_preview": [],
      "error": None,
    },
  ):
    result = run_multi_query_retrieval(plans, config)

  assert len(result["query_results"]) == 2
  assert result["total_estimated_bytes"] == 2000
  assert result["mode"] == "dry_run"


def test_matched_terms_assigned_on_execute(tmp_path) -> None:
  plan = _sample_plans()[0]
  config = RetrievalConfig(
    project_id="test-project",
    execute=True,
    output_dir=str(tmp_path),
    use_cache=False,
  )

  with patch(
    "tech_cartography.retrieval.bigquery_light_retriever.dry_run_query",
    return_value={
      "dry_run_status": "ok",
      "estimated_bytes": 1000,
      "estimated_gb": 0.0,
      "estimated_usd": 0.0,
      "would_be_blocked_by_max_bytes": False,
      "error": None,
    },
  ), patch(
    "tech_cartography.retrieval.bigquery_light_retriever.execute_query",
    return_value=[
      {
        "publication_number": "US-2024-000001",
        "title": "PAN carbon fiber carbonization",
        "abstract": "High modulus aerospace composite",
      },
    ],
  ):
    result = run_query_plan(plan, config)

  assert result["record_count"] == 1
  assert result["records"][0]["search_intent"] == plan.intent_id
  assert result["records"][0]["matched_terms"]
