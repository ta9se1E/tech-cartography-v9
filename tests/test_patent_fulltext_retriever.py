"""Tests for patent full text retriever."""

from __future__ import annotations

from unittest.mock import patch

from tech_cartography.retrieval.patent_fulltext_retriever import (
  FullTextRetrievalConfig,
  execute_fulltext_query,
  retrieve_controlled_fulltext_run,
  retrieve_fulltext_for_candidate,
  retrieve_fulltext_for_top_candidates,
  route_fulltext_candidate,
)
from tech_cartography.retrieval.fulltext_cache import save_fulltext_to_cache


class _FakeJob:
  def __init__(self, total_bytes: int = 1024**2) -> None:
    self.total_bytes_processed = total_bytes


class _FakeQueryJob:
  def __init__(self, rows: list[dict] | None = None) -> None:
    self._rows = rows or []

  def result(self) -> list[dict]:
    return self._rows


class _FakeClient:
  def __init__(self, rows: list[dict] | None = None, total_bytes: int = 1024**2) -> None:
    self.rows = rows or []
    self.total_bytes = total_bytes
    self.last_job_config = None

  def query(self, sql: str, job_config=None):  # noqa: ANN001
    self.last_job_config = job_config
    if job_config and getattr(job_config, "dry_run", False):
      return _FakeJob(self.total_bytes)
    return _FakeQueryJob(self.rows)


def _us_candidate() -> dict:
  return {
    "publication_number": "US2024000001A1",
    "title": "PAN carbon fiber",
    "assignee": "Toray",
    "country": "US",
    "claims_source": "not_fetched",
    "description_source": "not_fetched",
  }


def test_route_us_candidate() -> None:
  route = route_fulltext_candidate(_us_candidate())
  assert route["route"] == "us_bigquery_fulltext_candidate"


def test_route_jp_manual() -> None:
  route = route_fulltext_candidate(
    {"publication_number": "JP2020000001", "country": "JP"},
  )
  assert route["route"] == "manual_fulltext_required"


def test_config_defaults_safe() -> None:
  config = FullTextRetrievalConfig()
  assert config.dry_run is True
  assert config.execute is False


def test_execute_false_skips_bigquery_execution() -> None:
  config = FullTextRetrievalConfig(execute=False, use_cache=False)
  with patch(
    "tech_cartography.retrieval.patent_fulltext_retriever.dry_run_fulltext_query",
    return_value={
      "dry_run_status": "ok",
      "estimated_bytes": 1000,
      "would_be_blocked_by_max_bytes": False,
      "error": None,
    },
  ), patch(
    "tech_cartography.retrieval.patent_fulltext_retriever.execute_fulltext_query",
  ) as execute_mock:
    result = retrieve_fulltext_for_candidate(_us_candidate(), config)
  execute_mock.assert_not_called()
  assert result["retrieval_status"] == "dry_run_only"


def test_cache_hit_skips_execution(tmp_path) -> None:
  candidate = _us_candidate()
  save_fulltext_to_cache(
    {
      "publication_number": candidate["publication_number"],
      "claims": "Claim 1",
      "description": "Description",
      "evidence_coverage": {"has_claims": True, "has_description": True, "evidence_level": "medium_fulltext_evidence"},
      "evidence_level": "medium_fulltext_evidence",
      "source_route": "us_bigquery_fulltext_candidate",
    },
    str(tmp_path),
  )
  config = FullTextRetrievalConfig(cache_dir=str(tmp_path), use_cache=True)
  with patch(
    "tech_cartography.retrieval.patent_fulltext_retriever.execute_fulltext_query",
  ) as execute_mock:
    result = retrieve_fulltext_for_candidate(candidate, config)
  execute_mock.assert_not_called()
  assert result["retrieval_status"] == "cache_hit"


def test_blocked_by_cost_guard() -> None:
  config = FullTextRetrievalConfig(execute=True, use_cache=False)
  with patch(
    "tech_cartography.retrieval.patent_fulltext_retriever.dry_run_fulltext_query",
    return_value={
      "dry_run_status": "ok",
      "estimated_bytes": 10**12,
      "would_be_blocked_by_max_bytes": True,
      "error": None,
    },
  ), patch(
    "tech_cartography.retrieval.patent_fulltext_retriever.execute_fulltext_query",
  ) as execute_mock:
    result = retrieve_fulltext_for_candidate(_us_candidate(), config)
  execute_mock.assert_not_called()
  assert result["retrieval_status"] == "cost_guard_failed"


def test_execute_passes_maximum_bytes_billed() -> None:
  config = FullTextRetrievalConfig(execute=True, maximum_bytes_billed_gb=10.0, use_cache=False)
  fake_client = _FakeClient(
    rows=[
      {
        "publication_number": "US2024000001A1",
        "title": "PAN carbon fiber",
        "claims": "Claim 1. Method",
        "description": "Description with examples",
        "assignee": "Toray",
        "country_code": "US",
      },
    ],
  )

  def factory(project_id: str) -> _FakeClient:
    return fake_client

  with patch(
    "tech_cartography.retrieval.patent_fulltext_retriever.resolve_project_id",
    return_value={"project_id": "test-project", "source": "explicit", "error": None},
  ), patch(
    "tech_cartography.retrieval.patent_fulltext_retriever.dry_run_fulltext_query",
    return_value={
      "dry_run_status": "ok",
      "estimated_bytes": 1000,
      "would_be_blocked_by_max_bytes": False,
      "error": None,
    },
  ):
    execution = execute_fulltext_query(
      _us_candidate(),
      config,
      client_factory=factory,
    )
  assert execution["execution_status"] == "executed"
  assert fake_client.last_job_config.maximum_bytes_billed > 0


def test_cn_execute_returns_unsupported_country() -> None:
  config = FullTextRetrievalConfig(execute=True, use_cache=False)
  execution = execute_fulltext_query(
    {"publication_number": "CN121137864A", "country": "CN"},
    config,
  )
  assert execution["execution_status"] == "unsupported_country"


def test_controlled_run_keeps_cn_in_manual_package() -> None:
  top5 = [_us_candidate()]
  strategic = [
    {
      "publication_number": "CN-121137864-A",
      "title": "PAN carbon fiber",
      "assignee": "ZHONGFU SHENYING CARBON FIBER CO LTD",
      "country": "CN",
      "source_route": "manual_fulltext_required",
      "watch_reason_japanese": "中国候補",
    },
  ]
  config = FullTextRetrievalConfig(execute=False, use_cache=False)
  with patch(
    "tech_cartography.retrieval.patent_fulltext_retriever.dry_run_fulltext_query",
    return_value={
      "dry_run_status": "ok",
      "estimated_bytes": 1000,
      "would_be_blocked_by_max_bytes": False,
      "error": None,
    },
  ):
    result = retrieve_controlled_fulltext_run(top5, config, strategic_watch_candidates=strategic)
  assert result["dry_run_only_count"] >= 1
  assert result["strategic_watch_manual_count"] >= 1
  assert any(row.get("country") == "CN" for row in result["strategic_watch_manual_rows"])


def test_retrieval_status_fields_present() -> None:
  config = FullTextRetrievalConfig(execute=False, use_cache=False)
  with patch(
    "tech_cartography.retrieval.patent_fulltext_retriever.dry_run_fulltext_query",
    return_value={
      "dry_run_status": "ok",
      "estimated_bytes": 1000,
      "would_be_blocked_by_max_bytes": False,
      "error": None,
    },
  ):
    result = retrieve_fulltext_for_candidate(_us_candidate(), config)
  record = result["record"]
  assert record["retrieval_status"] == "dry_run_only"
  assert "claims_source" in record
  assert "evidence_coverage" in record
