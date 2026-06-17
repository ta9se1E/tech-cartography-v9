"""Tests for manual fulltext input schema (Phase 18A)."""

from __future__ import annotations

from tech_cartography.manual.manual_fulltext_input_schema import (
  ManualFulltextInput,
  load_manual_fulltext_input,
  save_manual_fulltext_input,
  validate_manual_fulltext_input,
)


def test_save_and_load_manual_input(tmp_path) -> None:
  entry = ManualFulltextInput(
    publication_number="US-12565719-B2",
    source_url="https://patents.google.com/patent/US12565719B2",
    claims_text="1. A fiber bundle.",
    entered_by="tester",
  )
  saved = save_manual_fulltext_input(entry, root=tmp_path)
  loaded = load_manual_fulltext_input("US-12565719-B2", root=tmp_path)
  assert loaded is not None
  assert loaded["claims_text"].startswith("1.")
  assert saved["path"]


def test_validation_requires_publication_number() -> None:
  warnings = validate_manual_fulltext_input({"publication_number": "", "claims_text": "x"})
  assert any("publication_number" in w for w in warnings)


def test_validation_warns_when_both_empty() -> None:
  warnings = validate_manual_fulltext_input(
    ManualFulltextInput(publication_number="US-1", claims_text="", description_text=""),
  )
  assert any("empty" in w for w in warnings)
