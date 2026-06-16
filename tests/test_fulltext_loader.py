"""Tests for manual full text loader."""

from tech_cartography.ingestion.fulltext_loader import (
  infer_sections_from_text,
  load_fulltext_file,
  parse_fulltext_text,
)


def test_infer_sections_from_markdown() -> None:
  text = """# Patent US2024000001A1
Claims
Claim 1. A carbon fiber method.

Description
Detailed process description.

Examples
Example 1: carbonization

Measured properties
5.5 GPa tensile strength
"""
  sections = infer_sections_from_text(text)
  assert "Claim 1" in sections["claims"]
  assert "Detailed process" in sections["description"]
  assert "Example 1" in sections["examples"]


def test_parse_fulltext_text() -> None:
  parsed = parse_fulltext_text("US2024000001A1", "Claims\nClaim 1.\nDescription\nBody")
  assert parsed["publication_number"] == "US2024000001A1"
  assert parsed["claims"]


def test_load_txt_file(tmp_path) -> None:
  path = tmp_path / "sample.md"
  path.write_text(
    "US2024000001A1\nClaims\nClaim 1.\nDescription\nBody text",
    encoding="utf-8",
  )
  records = load_fulltext_file(str(path))
  assert len(records) == 1
  assert records[0]["publication_number"]
