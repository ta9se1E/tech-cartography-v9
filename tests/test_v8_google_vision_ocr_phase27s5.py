"""Tests for Phase27S.5 Google Vision OCR fallback."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from tech_cartography.runtime.v8_google_vision_ocr_schema import (
  EXTRACTION_METHOD_VISION,
  OCR_HUMAN_REVIEW_WARNING,
)
from tech_cartography.runtime.v8_top5_pdf_pipeline_status_schema import Top5PdfPipelineStatus
from tech_cartography.services.v8_google_vision_ocr import (
  build_ocr_gcs_prefix,
  is_google_vision_ocr_enabled,
  parse_vision_ocr_json_outputs,
  run_google_vision_ocr_for_pdf,
  write_vision_ocr_outputs,
)
from tech_cartography.services.v8_top5_pdf_pipeline_status import infer_next_action

CASE_ID = "test_case_ocr_s5"
PUB = "CN108286090A"


def _sample_vision_json(text: str = "Example 1\nCarbon fiber precursor") -> dict:
  return {
    "responses": [
      {
        "fullTextAnnotation": {
          "text": text,
          "pages": [
            {
              "pageNumber": 1,
              "blocks": [
                {
                  "paragraphs": [
                    {
                      "words": [
                        {"symbols": [{"text": ch} for ch in text[:20]]},
                      ],
                    },
                  ],
                },
              ],
            },
          ],
        },
      },
    ],
  }


def test_is_google_vision_ocr_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv("ENABLE_GOOGLE_VISION_OCR", raising=False)
  assert is_google_vision_ocr_enabled() is False


def test_run_ocr_disabled_returns_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("ENABLE_GOOGLE_VISION_OCR", "false")
  pdf = tmp_path / f"{PUB}.pdf"
  pdf.write_bytes(b"%PDF")
  result = run_google_vision_ocr_for_pdf(CASE_ID, PUB, pdf, tmp_path / "outputs")
  assert result.status == "disabled"


def test_run_ocr_bucket_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("ENABLE_GOOGLE_VISION_OCR", "true")
  monkeypatch.delenv("GOOGLE_VISION_OCR_GCS_BUCKET", raising=False)
  pdf = tmp_path / f"{PUB}.pdf"
  pdf.write_bytes(b"%PDF")
  result = run_google_vision_ocr_for_pdf(CASE_ID, PUB, pdf, tmp_path / "outputs")
  assert result.status == "bucket_missing"


def test_build_ocr_gcs_prefix_includes_case_and_pub(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("GOOGLE_VISION_OCR_GCS_PREFIX", "tech-cartography-v8/ocr")
  prefix = build_ocr_gcs_prefix(CASE_ID, PUB)
  assert CASE_ID in prefix
  assert PUB in prefix


def test_parse_vision_json_outputs_pages(tmp_path: Path) -> None:
  json_path = tmp_path / "output-1.json"
  json_path.write_text(json.dumps(_sample_vision_json()), encoding="utf-8")
  pdf_path = tmp_path / f"{PUB}.pdf"
  result = parse_vision_ocr_json_outputs([json_path], CASE_ID, PUB, pdf_path)
  assert result.status == "ocr_completed"
  assert result.extracted_pages >= 1
  assert result.total_text_length > 0
  assert result.pages[0].extraction_method == EXTRACTION_METHOD_VISION
  assert result.pages[0].needs_human_review is True


def test_write_vision_ocr_publication_fulltext_raw_compatible(tmp_path: Path) -> None:
  json_path = tmp_path / "output-1.json"
  json_path.write_text(json.dumps(_sample_vision_json("PAN precursor carbonization")), encoding="utf-8")
  pdf_path = tmp_path / f"{PUB}.pdf"
  pdf_path.write_bytes(b"%PDF")
  result = parse_vision_ocr_json_outputs([json_path], CASE_ID, PUB, pdf_path)
  out_dir = write_vision_ocr_outputs(CASE_ID, [result], tmp_path / "outputs")
  raw_csv = out_dir / "publication_fulltext_raw.csv"
  assert raw_csv.exists()
  with raw_csv.open(encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))
  assert rows
  row = rows[0]
  assert row["extraction_method"] == EXTRACTION_METHOD_VISION
  assert row["needs_ocr"] == "False"
  assert OCR_HUMAN_REVIEW_WARNING in row["warning"]


def test_infer_next_action_needs_ocr_run_vision() -> None:
  status = Top5PdfPipelineStatus(
    case_id=CASE_ID,
    publication_number=PUB,
    pdf_uploaded=True,
    pdf_text_extracted=True,
    needs_ocr=True,
    vision_ocr_available=True,
    vision_ocr_text_extracted=False,
  )
  assert infer_next_action(status) == "Run Google Vision OCR or verify PDF text extraction"


def test_infer_next_action_ocr_disabled() -> None:
  status = Top5PdfPipelineStatus(
    case_id=CASE_ID,
    publication_number=PUB,
    pdf_uploaded=True,
    pdf_text_extracted=True,
    needs_ocr=True,
    vision_ocr_available=False,
  )
  assert infer_next_action(status) == "OCR disabled: enable Google Vision OCR"


def test_infer_next_action_extract_sections_from_ocr() -> None:
  status = Top5PdfPipelineStatus(
    case_id=CASE_ID,
    publication_number=PUB,
    pdf_uploaded=True,
    pdf_text_extracted=True,
    needs_ocr=True,
    vision_ocr_text_extracted=True,
    sections_extracted=False,
  )
  assert infer_next_action(status) == "Extract sections from OCR text"


def test_infer_next_action_extract_sections_from_ocr_when_stale() -> None:
  status = Top5PdfPipelineStatus(
    case_id=CASE_ID,
    publication_number=PUB,
    pdf_uploaded=True,
    pdf_text_extracted=True,
    needs_ocr=True,
    vision_ocr_text_extracted=True,
    sections_extracted=True,
    sections_stale_vs_ocr=True,
  )
  assert infer_next_action(status) == "Extract sections from OCR text"


def test_ocr_ui_importable() -> None:
  import tech_cartography.ui.v8_google_vision_ocr_ui as ocr_ui
  assert callable(ocr_ui.render_google_vision_ocr_section)
