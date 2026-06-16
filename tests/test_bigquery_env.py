"""Tests for BigQuery environment helpers."""

from tech_cartography.retrieval.bigquery_env import (
  bytes_to_gb,
  estimate_usd_from_bytes,
  gb_to_bytes,
  resolve_project_id,
)


def test_gb_to_bytes() -> None:
  assert gb_to_bytes(1) == 1073741824


def test_bytes_to_gb() -> None:
  assert abs(bytes_to_gb(1073741824) - 1.0) < 0.0001


def test_estimate_usd_from_bytes() -> None:
  one_tb = 1024**4
  assert abs(estimate_usd_from_bytes(one_tb, usd_per_tb=5.0) - 5.0) < 0.0001


def test_resolve_project_id_explicit() -> None:
  resolved = resolve_project_id("my-test-project")
  assert resolved["project_id"] == "my-test-project"
  assert resolved["source"] == "explicit"
