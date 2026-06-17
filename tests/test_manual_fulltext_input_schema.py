"""Tests for manual fulltext input schema (Phase 18B)."""

from __future__ import annotations

from tech_cartography.manual.manual_fulltext_input_schema import (
  ManualFulltextInput,
  load_manual_fulltext_input,
  normalize_manual_claims_text,
  save_manual_fulltext_input,
  validate_manual_fulltext_input,
)


def test_claims_only_input_is_valid_claims_only() -> None:
  validation = validate_manual_fulltext_input(
    ManualFulltextInput(
      publication_number="US-12565719-B2",
      claims_text="1. A carbon fiber comprising ...",
    ),
  )
  assert validation["validation_status"] == "valid_claims_only"
  assert validation["claims_present"] is True
  assert validation["description_present"] is False


def test_claims_and_description_input_is_valid_claims_and_description() -> None:
  validation = validate_manual_fulltext_input(
    ManualFulltextInput(
      publication_number="US-12565719-B2",
      claims_text="1. A fiber.",
      description_text="Detailed description.",
    ),
  )
  assert validation["validation_status"] == "valid_claims_and_description"
  assert validation["input_scope"] == "claims_and_description"


def test_empty_input_is_empty_input() -> None:
  validation = validate_manual_fulltext_input(
    ManualFulltextInput(publication_number="US-1", claims_text="", description_text=""),
  )
  assert validation["validation_status"] == "empty_input"


def test_publication_number_required() -> None:
  validation = validate_manual_fulltext_input({"publication_number": "", "claims_text": "x"})
  assert validation["validation_status"] == "invalid_publication_number"


def test_save_and_load_manual_input(tmp_path) -> None:
  entry = ManualFulltextInput(
    publication_number="US-12565719-B2",
    source_url="https://patents.google.com/patent/US12565719B2",
    claims_text="1. A fiber bundle.",
    entered_by="tester",
    input_route="manual_google_patents",
  )
  path = save_manual_fulltext_input(entry, tmp_path)
  loaded = load_manual_fulltext_input("US-12565719-B2", tmp_path)
  assert loaded is not None
  assert loaded.claims_text.startswith("1.")
  assert path.endswith("US-12565719-B2.json")


def test_normalize_manual_claims_text_strips_trailing_spaces() -> None:
  text = normalize_manual_claims_text("1. claim  \n\n2. dependent  ")
  assert text == "1. claim\n\n2. dependent"
