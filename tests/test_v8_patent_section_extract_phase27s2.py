"""Tests for Phase27S.2 patent fulltext section extraction."""

from __future__ import annotations

import ast
import csv
from pathlib import Path

import pytest

from tech_cartography.services.v8_patent_section_extract import (
  detect_patent_sections_for_publication,
  extract_sections_from_pdf_text_output,
  load_publication_fulltext_raw,
  normalize_fulltext_pages,
  write_section_outputs,
)

CASE_ID = "test_case_sections"
PUB = "CN108286090A"
PAD = " " * 50  # ensure sections exceed MIN_SECTION_TEXT_LENGTH


def _detect(fulltext: str) -> list:
  result = detect_patent_sections_for_publication(CASE_ID, PUB, fulltext)
  return result.sections


def test_detect_english_headings() -> None:
  text = f"""
Description
Detailed description paragraph with enough content.{PAD}

Example 1
Example one body with process conditions and results.{PAD}

Comparative Example 1
Comparative example body with baseline measurements.{PAD}

Table 1
Tabular data description with rows and columns listed.{PAD}
"""
  sections = _detect(text)
  types = [s.section_type for s in sections]
  assert "examples" in types
  assert "comparative_examples" in types
  assert "tables" in types
  example = next(s for s in sections if s.section_type == "examples")
  assert "Example" in (example.section_title or "")
  assert example.confidence >= 0.75


def test_detect_chinese_headings() -> None:
  text = f"""
说明书
本发明涉及一种碳纤维前驱体的处理方法。{PAD}

实施例1
以下说明具体的实施条件和测定结果。{PAD}

对比例1
以下说明比较例的处理条件和测定结果。{PAD}

表1
下表列出主要物性测定结果。{PAD}
"""
  sections = _detect(text)
  types = [s.section_type for s in sections]
  assert "description" in types
  assert "examples" in types
  assert "comparative_examples" in types
  assert "tables" in types


def test_detect_japanese_headings() -> None:
  text = f"""
明細書
本発明は炭素繊維前駆体に関する。{PAD}

実施例1
実施例の詳細な条件と結果を示す。{PAD}

比較例1
比較例の条件と結果を示す。{PAD}

表1
物性値の一覧を示す。{PAD}
"""
  sections = _detect(text)
  types = [s.section_type for s in sections]
  assert "examples" in types
  assert "comparative_examples" in types
  assert "tables" in types


def test_unknown_section_when_no_headings() -> None:
  text = "plain text without any recognizable patent section headings at all"
  result = detect_patent_sections_for_publication(CASE_ID, PUB, text)
  assert result.section_count >= 1
  assert any(s.section_type == "unknown" for s in result.sections)
  assert result.needs_human_review is True
  assert result.sections[0].confidence == 0.30


def test_confidence_and_needs_human_review() -> None:
  text = f"""
Technical Field
Field of carbon fiber precursor technology.{PAD}

Example 1
Detailed working example with sufficient text length.{PAD}
"""
  result = detect_patent_sections_for_publication(CASE_ID, PUB, text)
  for section in result.sections:
    assert 0.0 <= section.confidence <= 1.0
    assert isinstance(section.needs_human_review, bool)
  assert result.has_examples is True
  assert result.examples_count >= 1


def test_write_section_outputs(tmp_path: Path) -> None:
  result = detect_patent_sections_for_publication(
    CASE_ID,
    PUB,
    f"Example 1\nBody text with enough characters for section review.{PAD}",
  )
  out_dir = write_section_outputs(CASE_ID, [result], tmp_path / "outputs")
  assert (out_dir / "publication_fulltext_sections.csv").exists()
  assert (out_dir / "section_extraction_summary.csv").exists()
  assert (out_dir / "publication_fulltext_sections.md").exists()
  assert (out_dir / "section_extraction_summary.md").exists()

  with (out_dir / "section_extraction_summary.csv").open(encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
  assert rows[0]["publication_number"] == PUB


def test_extract_from_raw_csv(tmp_path: Path) -> None:
  raw_csv = tmp_path / "publication_fulltext_raw.csv"
  with raw_csv.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=[
      "case_id", "publication_number", "source_file", "page_no", "text",
      "text_length", "extraction_method", "needs_ocr", "warning",
    ])
    writer.writeheader()
    writer.writerow({
      "case_id": CASE_ID,
      "publication_number": PUB,
      "source_file": "/tmp/x.pdf",
      "page_no": 1,
      "text": f"实施例1\n实施例本文です。{PAD}",
      "text_length": 100,
      "extraction_method": "pypdf",
      "needs_ocr": False,
      "warning": "",
    })

  rows = load_publication_fulltext_raw(raw_csv)
  merged = normalize_fulltext_pages(rows)
  assert PUB in merged

  results = extract_sections_from_pdf_text_output(CASE_ID, raw_csv, tmp_path / "outputs")
  assert len(results) == 1
  assert results[0].has_examples is True


def test_no_llm_ocr_imports() -> None:
  import tech_cartography.services.v8_patent_section_extract as mod

  tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
  modules: set[str] = set()
  for node in ast.walk(tree):
    if isinstance(node, ast.Import):
      modules.update(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module:
      modules.add(node.module)
  joined = " ".join(modules).lower()
  assert "openai" not in joined
  assert "gemini" not in joined
  assert "tesseract" not in joined
