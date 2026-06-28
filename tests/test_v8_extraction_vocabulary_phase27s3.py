"""Tests for Phase27S.3 extraction vocabulary."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.services.v8_extraction_vocabulary import (
  CASE_01_ID,
  build_vocabulary_context_for_prompt,
  get_default_extraction_vocabulary,
  load_extraction_vocabulary,
  parse_keyword_text,
  save_extraction_vocabulary,
)

def test_default_vocabulary_case1() -> None:
  vocab = get_default_extraction_vocabulary(CASE_01_ID)
  assert vocab.case_id == CASE_01_ID
  assert "PAN" in vocab.material_keywords
  assert "carbonization" in vocab.process_keywords
  assert "tensile strength" in vocab.property_keywords
  assert len(vocab.material_keywords) >= 10


def test_parse_keyword_text_newline_and_comma() -> None:
  parsed = parse_keyword_text("PAN, carbonization\ngraphitization, PAN")
  assert parsed == ["PAN", "carbonization", "graphitization"]


def test_parse_keyword_text_strips_empty() -> None:
  assert parse_keyword_text("  , \n , alpha") == ["alpha"]


def test_save_and_load_vocabulary(tmp_path: Path) -> None:
  vocab = get_default_extraction_vocabulary(CASE_01_ID)
  vocab.material_keywords = ["custom_material"]
  path = save_extraction_vocabulary(CASE_01_ID, tmp_path, vocab)
  assert path.exists()
  loaded = load_extraction_vocabulary(CASE_01_ID, tmp_path)
  assert loaded.material_keywords == ["custom_material"]
  data = json.loads(path.read_text(encoding="utf-8"))
  assert data["case_id"] == CASE_01_ID


def test_build_vocabulary_context_for_prompt() -> None:
  vocab = get_default_extraction_vocabulary(CASE_01_ID)
  context = build_vocabulary_context_for_prompt(vocab)
  assert "Material keywords" in context
  assert "Process keywords" in context
  assert "Property keywords" in context
  assert "PAN" in context
  assert "hints only" in context
