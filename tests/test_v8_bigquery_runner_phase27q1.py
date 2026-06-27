"""Phase27Q.1 BigQuery runner tests."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.runtime.v8_research_theme_schema import ResearchThemeProfile
from tech_cartography.services.v8_bigquery_runner import FakeBigQueryClient, run_bigquery_candidate_search
from tech_cartography.services.v8_bigquery_safety import BigQuerySafetyConfig


def _enabled_cfg(*, allow_execute: bool = False) -> BigQuerySafetyConfig:
  return BigQuerySafetyConfig(
    enable_bigquery_run=True,
    show_bigquery_admin=True,
    bigquery_project_id="test-project",
    bigquery_location="US",
    bigquery_max_bytes_billed=5_000_000_000,
    bigquery_default_limit=100,
    bigquery_dry_run_only=not allow_execute,
    bigquery_allow_execute=allow_execute,
  )


def test_generate_sql_without_auth(tmp_path: Path) -> None:
  profile = ResearchThemeProfile(case_id="case_01", core_keywords=["PAN"], seed_publication_numbers=[])
  manifest = run_bigquery_candidate_search(
    case_id="case_01",
    theme_profile=profile,
    mode="generate_sql",
    project_root=tmp_path,
  )
  assert manifest.sql_path
  assert Path(manifest.sql_path).exists()


def test_dry_run_with_fake_client(tmp_path) -> None:
  profile = ResearchThemeProfile(case_id="case_01", core_keywords=["PAN"])
  client = FakeBigQueryClient(total_bytes=2048)
  manifest = run_bigquery_candidate_search(
    case_id="case_01",
    theme_profile=profile,
    mode="dry_run",
    project_root=tmp_path,
    client=client,
    config=_enabled_cfg(),
  )
  assert client.last_dry_run is True
  assert manifest.dry_run_path


def test_execute_with_fake_client(tmp_path) -> None:
  profile = ResearchThemeProfile(case_id="case_01", core_keywords=["PAN"])
  client = FakeBigQueryClient(
    total_bytes=2048,
    rows=[{"publication_number": "JP2022090764A", "title": "test", "publication_date": "20220101", "heuristic_score": 10}],
  )
  manifest = run_bigquery_candidate_search(
    case_id="case_01",
    theme_profile=profile,
    mode="execute",
    project_root=tmp_path,
    client=client,
    config=_enabled_cfg(allow_execute=True),
  )
  assert manifest.large_candidate_csv_path
