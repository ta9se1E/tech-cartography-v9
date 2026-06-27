"""Phase27Q.1 BigQuery safety gate tests."""

from __future__ import annotations

import pytest

from tech_cartography.services.v8_bigquery_safety import (
  BigQuerySafetyConfig,
  assert_dry_run_allowed,
  assert_execute_allowed,
  clamp_limit,
)


def test_execute_rejected_when_disabled() -> None:
  cfg = BigQuerySafetyConfig(
    enable_bigquery_run=False,
    show_bigquery_admin=False,
    bigquery_project_id="",
    bigquery_location="US",
    bigquery_max_bytes_billed=1_000_000_000,
    bigquery_default_limit=1000,
    bigquery_dry_run_only=True,
    bigquery_allow_execute=False,
  )
  with pytest.raises(PermissionError, match="ENABLE_BIGQUERY_RUN"):
    assert_execute_allowed(cfg)


def test_execute_rejected_without_allow_execute() -> None:
  cfg = BigQuerySafetyConfig(
    enable_bigquery_run=True,
    show_bigquery_admin=True,
    bigquery_project_id="proj",
    bigquery_location="US",
    bigquery_max_bytes_billed=1_000_000_000,
    bigquery_default_limit=1000,
    bigquery_dry_run_only=False,
    bigquery_allow_execute=False,
  )
  with pytest.raises(PermissionError, match="BIGQUERY_ALLOW_EXECUTE"):
    assert_execute_allowed(cfg)


def test_dry_run_rejected_without_max_bytes() -> None:
  cfg = BigQuerySafetyConfig(
    enable_bigquery_run=True,
    show_bigquery_admin=True,
    bigquery_project_id="proj",
    bigquery_location="US",
    bigquery_max_bytes_billed=0,
    bigquery_default_limit=1000,
    bigquery_dry_run_only=True,
    bigquery_allow_execute=False,
  )
  with pytest.raises(PermissionError, match="MAX_BYTES"):
    assert_dry_run_allowed(cfg)


def test_clamp_limit() -> None:
  assert clamp_limit(5000) == 1000
