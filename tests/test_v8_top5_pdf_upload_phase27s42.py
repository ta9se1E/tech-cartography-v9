"""Tests for Phase27S.4.2 Top5 PDF upload in Deep Dive."""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import patch

import pytest

from tech_cartography.runtime.v8_top5_pdf_pipeline_status_schema import Top5PdfPipelineStatus
from tech_cartography.services.v8_patent_pdf_storage import (
  get_patent_pdf_path,
  save_uploaded_patent_pdf,
)
from tech_cartography.services.v8_top5_pdf_pipeline_status import infer_next_action

CASE_ID = "test_case_pdf_upload_s42"
PUB_TOP5 = "CN108286090A"
PUB_OTHER = "US9999999A"


def test_deep_dive_ui_has_upload_section() -> None:
  mod = importlib.import_module("tech_cartography.ui.v8_top5_pdf_deep_dive_ui")
  assert hasattr(mod, "render_top5_pdf_upload_section")
  assert callable(mod.render_top5_pdf_upload_section)


def test_save_uploaded_patent_pdf_writes_expected_path(tmp_path: Path) -> None:
  with patch(
    "tech_cartography.services.v8_patent_pdf_storage.load_top5_publications",
    return_value=[PUB_TOP5],
  ):
    out = save_uploaded_patent_pdf(
      CASE_ID,
      tmp_path,
      PUB_TOP5,
      b"%PDF-1.4 test",
      original_filename="test.pdf",
      allowed_publications=[PUB_TOP5],
    )
  expected = tmp_path / "cases" / CASE_ID / "patent_pdfs" / f"{PUB_TOP5}.pdf"
  assert out == expected
  assert expected.exists()
  assert expected.read_bytes().startswith(b"%PDF")


def test_save_uploaded_patent_pdf_rejects_non_top5(tmp_path: Path) -> None:
  with pytest.raises(ValueError, match="Top5"):
    save_uploaded_patent_pdf(
      CASE_ID,
      tmp_path,
      PUB_OTHER,
      b"%PDF",
      allowed_publications=[PUB_TOP5],
    )


def test_get_patent_pdf_path_format(tmp_path: Path) -> None:
  path = get_patent_pdf_path(CASE_ID, tmp_path, PUB_TOP5)
  assert path == tmp_path / "cases" / CASE_ID / "patent_pdfs" / f"{PUB_TOP5}.pdf"


def test_old_input_tab_upload_copy_removed_from_ui_sources() -> None:
  root = Path("src/tech_cartography")
  forbidden = "入力・テーマ設定」のPDFアップロード欄"
  for rel in (
    "ui/v8_google_patents_links_ui.py",
    "runtime/v8_google_patents_links_schema.py",
    "ui/v8_top5_pdf_deep_dive_ui.py",
    "ui/v8_top5_reading_ui.py",
  ):
    text = (root / rel).read_text(encoding="utf-8")
    assert forbidden not in text


def test_infer_next_action_needs_ocr() -> None:
  status = Top5PdfPipelineStatus(
    case_id=CASE_ID,
    publication_number=PUB_TOP5,
    pdf_uploaded=True,
    pdf_text_extracted=True,
    needs_ocr=True,
    vision_ocr_available=True,
  )
  action = infer_next_action(status)
  assert action == "Run Google Vision OCR"


def test_needs_ocr_does_not_expose_primary_extract_sections_button() -> None:
  source = Path("src/tech_cartography/ui/v8_top5_pdf_deep_dive_ui.py").read_text(encoding="utf-8")
  assert "render_google_vision_ocr_section" in source
  assert "Extract sections anyway" not in source
