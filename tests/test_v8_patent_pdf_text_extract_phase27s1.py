"""Tests for Phase27S.1 patent PDF text extraction."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tech_cartography.runtime.v8_patent_pdf_text_schema import (
  PatentPdfTextExtractionResult,
  PatentPdfTextPage,
)
from tech_cartography.services.v8_patent_pdf_text_extract import (
  _pypdf_available,
  extract_text_from_pdf,
  extract_text_from_uploaded_top5_pdfs,
  find_uploaded_patent_pdfs,
  infer_publication_number_from_pdf_path,
  write_pdf_text_outputs,
)

CASE_ID = "test_case_pdf_extract"


def test_find_uploaded_patent_pdfs(tmp_path: Path) -> None:
  pdf_dir = tmp_path / "cases" / CASE_ID / "patent_pdfs"
  pdf_dir.mkdir(parents=True)
  (pdf_dir / "CN108286090A.pdf").write_bytes(b"%PDF-1.4\n")
  (pdf_dir / "CN117987966A.pdf").write_bytes(b"%PDF-1.4\n")

  found = find_uploaded_patent_pdfs(CASE_ID, tmp_path)
  assert len(found) == 2
  assert all(p.suffix == ".pdf" for p in found)


def test_infer_publication_number_from_pdf_path() -> None:
  assert infer_publication_number_from_pdf_path(Path("CN108286090A.pdf")) == "CN108286090A"
  assert infer_publication_number_from_pdf_path(Path("/tmp/cn108286090a.pdf")) == "CN108286090A"


def test_extract_text_from_missing_pdf(tmp_path: Path) -> None:
  missing = tmp_path / "missing.pdf"
  result = extract_text_from_pdf(missing, CASE_ID, "CN108286090A")
  assert result.status == "file_missing"
  assert result.needs_ocr is True
  assert result.warning is not None


def test_extract_text_from_invalid_pdf_graceful(tmp_path: Path) -> None:
  bad = tmp_path / "bad.pdf"
  bad.write_bytes(b"not a pdf")
  result = extract_text_from_pdf(bad, CASE_ID, "CN108286090A")
  assert result.status in {"error", "needs_ocr", "empty", "library_missing"}
  assert isinstance(result, PatentPdfTextExtractionResult)


def test_extraction_result_schema_fields() -> None:
  page = PatentPdfTextPage(
    case_id=CASE_ID,
    publication_number="CN108286090A",
    source_file="/tmp/x.pdf",
    page_no=1,
    text="hello",
    text_length=5,
    extraction_method="pypdf",
    needs_ocr=False,
  )
  result = PatentPdfTextExtractionResult(
    case_id=CASE_ID,
    publication_number="CN108286090A",
    source_file="/tmp/x.pdf",
    page_count=1,
    total_text_length=5,
    extracted_pages=1,
    pages=[page],
    status="ok",
  )
  d = result.to_dict()
  assert d["case_id"] == CASE_ID
  assert d["pages"][0]["text_length"] == 5
  assert "needs_ocr" in d


def test_write_pdf_text_outputs(tmp_path: Path) -> None:
  page = PatentPdfTextPage(
    case_id=CASE_ID,
    publication_number="CN108286090A",
    source_file=str(tmp_path / "x.pdf"),
    page_no=1,
    text="PAN precursor",
    text_length=13,
    extraction_method="pypdf",
    needs_ocr=False,
  )
  result = PatentPdfTextExtractionResult(
    case_id=CASE_ID,
    publication_number="CN108286090A",
    source_file=str(tmp_path / "x.pdf"),
    page_count=1,
    total_text_length=13,
    extracted_pages=1,
    pages=[page],
    status="ok",
  )
  out_dir = write_pdf_text_outputs(CASE_ID, [result], tmp_path / "outputs")
  assert (out_dir / "publication_fulltext_raw.csv").exists()
  assert (out_dir / "publication_fulltext_raw.md").exists()
  assert (out_dir / "pdf_text_extraction_summary.csv").exists()
  assert (out_dir / "pdf_text_extraction_summary.md").exists()
  csv_text = (out_dir / "publication_fulltext_raw.csv").read_text(encoding="utf-8")
  assert "PAN precursor" in csv_text
  assert "publication_number" in csv_text


def test_extract_top5_no_gemini_openai_ocr() -> None:
  """Ensure extraction path does not import LLM/OCR clients."""
  import ast
  import tech_cartography.services.v8_patent_pdf_text_extract as mod

  tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
  modules: set[str] = set()
  for node in ast.walk(tree):
    if isinstance(node, ast.Import):
      modules.update(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom):
      if node.module:
        modules.add(node.module)
  joined = " ".join(modules).lower()
  assert "openai" not in joined
  assert "gemini" not in joined
  assert "tesseract" not in joined


def test_extract_top5_missing_pdfs(tmp_path: Path) -> None:
  results = extract_text_from_uploaded_top5_pdfs(
    CASE_ID,
    tmp_path,
    publication_numbers=["CN108286090A"],
  )
  assert len(results) == 1
  assert results[0].status == "file_missing"


@pytest.mark.skipif(not _pypdf_available(), reason="pypdf not installed")
def test_extract_text_from_minimal_pdf(tmp_path: Path) -> None:
  from pypdf import PdfWriter

  pdf_path = tmp_path / "CN108286090A.pdf"
  writer = PdfWriter()
  writer.add_blank_page(width=200, height=200)
  with pdf_path.open("wb") as handle:
    writer.write(handle)

  result = extract_text_from_pdf(pdf_path, CASE_ID, "CN108286090A")
  assert result.status in {"needs_ocr", "empty", "ok"}
  assert result.page_count >= 1


def test_library_missing_status(tmp_path: Path) -> None:
  pdf_path = tmp_path / "x.pdf"
  pdf_path.write_bytes(b"%PDF-1.4\n")
  with patch(
    "tech_cartography.services.v8_patent_pdf_text_extract._pypdf_available",
    return_value=False,
  ):
    result = extract_text_from_pdf(pdf_path, CASE_ID, "CN108286090A")
  assert result.status == "library_missing"
  assert "pypdf" in (result.warning or "")
