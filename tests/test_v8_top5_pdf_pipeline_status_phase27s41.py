"""Tests for Phase27S.4.1 Top5 PDF pipeline status aggregator."""

from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import patch

import pytest

from tech_cartography.runtime.v8_top5_pdf_pipeline_status_schema import Top5PdfPipelineStatus
from tech_cartography.services.v8_top5_pdf_pipeline_status import (
  build_top5_pdf_pipeline_status,
  find_latest_claim_example_binding_summary,
  find_latest_example_facts_summary,
  find_latest_pdf_text_summary,
  find_latest_section_summary,
  infer_next_action,
)

CASE_ID = "test_case_pipeline_s41"
PUB_A = "CN108286090A"
PUB_B = "CN117987966A"


def _status(**kwargs: object) -> Top5PdfPipelineStatus:
  defaults = {
    "case_id": CASE_ID,
    "publication_number": PUB_A,
  }
  defaults.update(kwargs)
  return Top5PdfPipelineStatus(**defaults)  # type: ignore[arg-type]


def test_infer_next_action_pdf_not_uploaded() -> None:
  assert infer_next_action(_status(pdf_uploaded=False)) == "PDFを取得してアップロード"


def test_infer_next_action_text_not_extracted() -> None:
  assert infer_next_action(_status(pdf_uploaded=True, pdf_text_extracted=False)) == "Extract PDF text"


def test_infer_next_action_needs_ocr() -> None:
  s = _status(
    pdf_uploaded=True,
    pdf_text_extracted=True,
    needs_ocr=True,
    vision_ocr_available=True,
  )
  assert infer_next_action(s) == "Run Google Vision OCR"


def test_infer_next_action_sections_not_extracted() -> None:
  s = _status(pdf_uploaded=True, pdf_text_extracted=True, sections_extracted=False)
  assert infer_next_action(s) == "Extract sections"


def test_infer_next_action_examples_missing() -> None:
  s = _status(
    pdf_uploaded=True,
    pdf_text_extracted=True,
    sections_extracted=True,
    has_examples=False,
    examples_count=0,
  )
  assert infer_next_action(s) == "examples未検出: セクション抽出結果を確認してください"


def test_infer_next_action_facts_not_extracted() -> None:
  s = _status(
    pdf_uploaded=True,
    pdf_text_extracted=True,
    sections_extracted=True,
    has_examples=True,
    examples_count=2,
    example_facts_extracted=False,
  )
  assert infer_next_action(s) == "Extract example facts"


def test_infer_next_action_binding_not_generated() -> None:
  s = _status(
    pdf_uploaded=True,
    pdf_text_extracted=True,
    sections_extracted=True,
    has_examples=True,
    example_facts_extracted=True,
    claim_example_links_generated=False,
  )
  assert infer_next_action(s) == "Bind claim to example facts"


def test_infer_next_action_complete() -> None:
  s = _status(
    pdf_uploaded=True,
    pdf_text_extracted=True,
    sections_extracted=True,
    has_examples=True,
    example_facts_extracted=True,
    claim_example_links_generated=True,
  )
  assert infer_next_action(s) == "Gapロジック更新へ進めます"


def test_find_latest_summaries_missing_graceful(tmp_path: Path) -> None:
  assert find_latest_pdf_text_summary(CASE_ID, tmp_path / "outputs") is None
  assert find_latest_section_summary(CASE_ID, tmp_path / "outputs") is None
  assert find_latest_example_facts_summary(CASE_ID, tmp_path / "outputs") is None
  assert find_latest_claim_example_binding_summary(CASE_ID, tmp_path / "outputs") is None


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  with path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)


def test_build_top5_pdf_pipeline_status_empty_outputs(tmp_path: Path) -> None:
  pdf_dir = tmp_path / "cases" / CASE_ID / "patent_pdfs"
  pdf_dir.mkdir(parents=True)
  (pdf_dir / f"{PUB_A}.pdf").write_bytes(b"%PDF")

  with patch(
    "tech_cartography.services.v8_top5_pdf_pipeline_status.load_top5_publications",
    return_value=[PUB_A],
  ):
    statuses = build_top5_pdf_pipeline_status(CASE_ID, tmp_path, tmp_path / "outputs")
  assert len(statuses) == 1
  assert statuses[0].publication_number == PUB_A
  assert statuses[0].pdf_uploaded is True
  assert statuses[0].next_action == "Extract PDF text"


def test_build_top5_pdf_pipeline_status_with_summaries(tmp_path: Path) -> None:
  text_dir = tmp_path / "outputs" / "local_v8_pdf_text_extract" / f"{CASE_ID}_t1"
  text_dir.mkdir(parents=True)
  _write_csv(
    text_dir / "pdf_text_extraction_summary.csv",
    ["publication_number", "status", "total_text_length", "needs_ocr"],
    [{"publication_number": PUB_A, "status": "ok", "total_text_length": "5000", "needs_ocr": "false"}],
  )

  sec_dir = tmp_path / "outputs" / "local_v8_patent_sections" / f"{CASE_ID}_s1"
  sec_dir.mkdir(parents=True)
  _write_csv(
    sec_dir / "section_extraction_summary.csv",
    [
      "publication_number", "status", "section_count", "examples_count",
      "comparative_examples_count", "tables_count", "has_examples", "needs_human_review",
    ],
    [{
      "publication_number": PUB_A,
      "status": "ok",
      "section_count": "4",
      "examples_count": "2",
      "comparative_examples_count": "0",
      "tables_count": "1",
      "has_examples": "true",
      "needs_human_review": "false",
    }],
  )
  _write_csv(
    sec_dir / "publication_fulltext_sections.csv",
    [
      "case_id", "publication_number", "section_id", "section_type", "section_title",
      "page_start", "page_end", "text_length", "needs_human_review",
    ],
    [{
      "case_id": CASE_ID,
      "publication_number": PUB_A,
      "section_id": "s1",
      "section_type": "examples",
      "section_title": "Examples",
      "page_start": "1",
      "page_end": "2",
      "text_length": "100",
      "needs_human_review": "false",
    }],
  )

  facts_dir = tmp_path / "outputs" / "local_v8_example_facts" / f"{CASE_ID}_f1"
  facts_dir.mkdir(parents=True)
  _write_csv(
    facts_dir / "example_facts_summary.csv",
    [
      "publication_number", "fact_count", "property_fact_count",
      "process_condition_fact_count", "matched_user_keyword_count", "needs_human_review",
    ],
    [{
      "publication_number": PUB_A,
      "fact_count": "3",
      "property_fact_count": "1",
      "process_condition_fact_count": "2",
      "matched_user_keyword_count": "2",
      "needs_human_review": "true",
    }],
  )

  bind_dir = tmp_path / "outputs" / "local_v8_claim_example_links" / f"{CASE_ID}_b1"
  bind_dir.mkdir(parents=True)
  _write_csv(
    bind_dir / "claim_example_binding_summary.csv",
    [
      "publication_number", "link_count", "linked_claim_count",
      "unlinked_claim_count", "needs_human_review",
    ],
    [{
      "publication_number": PUB_A,
      "link_count": "5",
      "linked_claim_count": "3",
      "unlinked_claim_count": "2",
      "needs_human_review": "true",
    }],
  )

  pdf_dir = tmp_path / "cases" / CASE_ID / "patent_pdfs"
  pdf_dir.mkdir(parents=True)
  (pdf_dir / f"{PUB_A}.pdf").write_bytes(b"%PDF")

  with patch(
    "tech_cartography.services.v8_top5_pdf_pipeline_status.load_top5_publications",
    return_value=[PUB_A],
  ):
    statuses = build_top5_pdf_pipeline_status(CASE_ID, tmp_path, tmp_path / "outputs")

  assert len(statuses) == 1
  s = statuses[0]
  assert s.pdf_text_extracted is True
  assert s.sections_extracted is True
  assert s.example_facts_extracted is True
  assert s.claim_example_links_generated is True
  assert s.next_action == "Gapロジック更新へ進めます"
  assert s.linked_claim_count == 3
