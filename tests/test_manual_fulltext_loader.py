"""Tests for manual fulltext loader (Phase 18B)."""

from __future__ import annotations

from tech_cartography.manual.manual_fulltext_input_schema import ManualFulltextInput, save_manual_fulltext_input
from tech_cartography.manual.manual_fulltext_loader import (
  apply_manual_fulltext_fallback,
  convert_manual_input_to_fulltext_record,
  load_manual_fulltext_as_record,
  merge_manual_fulltext_with_metadata,
)


def test_convert_manual_claims_to_fulltext_record_dict() -> None:
  manual = ManualFulltextInput(
    publication_number="US-12565719-B2",
    claims_text="1. A carbon fiber comprising PAN precursor.",
    input_route="manual_google_patents",
    validation_status="valid_claims_only",
  )
  record = convert_manual_input_to_fulltext_record(manual)
  assert record["publication_number"] == "US-12565719-B2"
  assert record["claims_length"] > 0
  assert record["retrieval_status"] == "manual_claims_loaded"
  assert record["fulltext_source"] == "manual_input"
  assert record["evidence_level"] == "low_fulltext_evidence"


def test_evidence_level_claims_only_without_description() -> None:
  manual = ManualFulltextInput(
    publication_number="US-1",
    claims_text="1. A method.",
    validation_status="valid_claims_only",
  )
  record = convert_manual_input_to_fulltext_record(manual)
  coverage = record["evidence_coverage"]
  assert coverage["description_support"] == "limited_no_description"
  assert coverage["examples_support"] == "not_available"


def test_merge_manual_fulltext_with_metadata() -> None:
  manual_record = {
    "publication_number": "US-1",
    "claims": "1. Fiber.",
    "claims_length": 10,
    "retrieval_status": "manual_claims_loaded",
  }
  metadata = {
    "publication_number": "US-1",
    "title": "Carbon fiber",
    "assignee": "Toray",
    "retrieval_status": "not_found",
  }
  merged = merge_manual_fulltext_with_metadata(manual_record, metadata)
  assert merged["title"] == "Carbon fiber"
  assert merged["claims"] == "1. Fiber."
  assert merged["retrieval_status"] == "manual_claims_loaded"


def test_description_missing_still_ready_via_loader(tmp_path) -> None:
  save_manual_fulltext_input(
    ManualFulltextInput(
      publication_number="US-12565719-B2",
      claims_text="1. A carbon fiber.",
      input_route="manual_google_patents",
    ),
    tmp_path,
  )
  record = load_manual_fulltext_as_record("US-12565719-B2", tmp_path)
  assert record is not None
  assert record["claims_length"] > 0
  assert record["description_length"] == 0


def test_apply_manual_fallback_overrides_not_found(tmp_path) -> None:
  save_manual_fulltext_input(
    ManualFulltextInput(
      publication_number="US-12565719-B2",
      claims_text="1. A carbon fiber comprising ...",
      input_route="manual_google_patents",
    ),
    tmp_path,
  )
  records = [
    {
      "publication_number": "US-12565719-B2",
      "title": "Carbon fiber",
      "retrieval_status": "not_found",
      "claims": "",
    },
  ]
  updated, applied = apply_manual_fulltext_fallback(records, input_dir=tmp_path)
  assert len(applied) == 1
  assert updated[0]["retrieval_status"] == "manual_claims_loaded"
  assert updated[0]["claims_length"] > 0
