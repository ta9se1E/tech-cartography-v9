"""Tests for BigQuery fulltext availability probe (Phase 18A)."""

from __future__ import annotations

import json

from tech_cartography.retrieval.bigquery_fulltext_availability_probe import (
  classify_probe_result,
  probe_result_to_public_dict,
)


def test_classify_found_claims() -> None:
  result = classify_probe_result(
    "US-12565719-B2",
    [{"publication_number": "US-12565719-B2", "claims_length_estimate": 1200, "description_length_estimate": 0}],
    variants_checked=["US-12565719-B2"],
    scope="claims_only",
  )
  assert result.probe_status == "found_claims"
  assert result.has_claims is True


def test_classify_not_found() -> None:
  result = classify_probe_result(
    "US-12565719-B2",
    [],
    variants_checked=["US-12565719-B2", "US12565719B2"],
    scope="claims_only",
  )
  assert result.probe_status == "not_found_in_bigquery"
  assert result.has_publication_row is False


def test_skipped_due_to_probe_cost() -> None:
  result = classify_probe_result(
    "US-1",
    [],
    variants_checked=["US-1"],
    scope="claims_only",
    skipped_due_to_cost=True,
  )
  assert result.probe_status == "skipped_due_to_probe_cost"


def test_public_result_has_no_amounts() -> None:
  result = classify_probe_result(
    "US-1",
    [],
    variants_checked=["US-1"],
    scope="claims_only",
  )
  result.estimated_usd = 1.23
  result.estimated_bytes = 999
  public = probe_result_to_public_dict(result)
  blob = json.dumps(public, ensure_ascii=False).lower()
  assert "usd" not in blob
  assert "1.23" not in blob
