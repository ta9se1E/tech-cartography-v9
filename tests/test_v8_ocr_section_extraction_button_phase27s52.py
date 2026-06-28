"""Tests for Phase27S.5.2 OCR section extraction button / pipeline status."""

from __future__ import annotations

import csv
import importlib
from pathlib import Path
from unittest.mock import patch

import pytest

from tech_cartography.runtime.v8_google_vision_ocr_schema import EXTRACTION_METHOD_VISION
from tech_cartography.runtime.v8_top5_pdf_pipeline_status_schema import Top5PdfPipelineStatus
from tech_cartography.services.v8_patent_section_extract import (
  find_publication_fulltext_raw_pack,
  sections_stale_vs_ocr_output,
)
from tech_cartography.services.v8_top5_pdf_pipeline_status import infer_next_action

CASE_ID = "test_case_ocr_s52"
PUB = "CN108286090A"


def _status(**kwargs: object) -> Top5PdfPipelineStatus:
  defaults = {
    "case_id": CASE_ID,
    "publication_number": PUB,
    "pdf_uploaded": True,
    "pdf_text_extracted": True,
    "needs_ocr": True,
  }
  defaults.update(kwargs)
  return Top5PdfPipelineStatus(**defaults)  # type: ignore[arg-type]


def _write_ocr_raw_csv(path: Path, *, pages: int = 9, chars_per_page: int = 100) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  with path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(
      handle,
      fieldnames=[
        "case_id", "publication_number", "source_file", "page_no", "text",
        "text_length", "extraction_method", "needs_ocr", "warning",
      ],
    )
    writer.writeheader()
    for page_no in range(1, pages + 1):
      text = "x" * chars_per_page
      writer.writerow({
        "case_id": CASE_ID,
        "publication_number": PUB,
        "source_file": f"/tmp/{PUB}.pdf",
        "page_no": page_no,
        "text": text,
        "text_length": len(text),
        "extraction_method": EXTRACTION_METHOD_VISION,
        "needs_ocr": False,
        "warning": "OCR text requires human review",
      })


def test_infer_next_action_ocr_done_sections_missing() -> None:
  s = _status(
    vision_ocr_text_extracted=True,
    sections_extracted=False,
  )
  assert infer_next_action(s) == "Extract sections from OCR text"


def test_infer_next_action_ocr_done_sections_stale() -> None:
  s = _status(
    vision_ocr_text_extracted=True,
    sections_extracted=True,
    sections_stale_vs_ocr=True,
  )
  assert infer_next_action(s) == "Extract sections from OCR text"


def test_infer_next_action_prefers_ocr_sections_over_rerun_ocr() -> None:
  s = _status(
    needs_ocr=True,
    vision_ocr_text_extracted=True,
    sections_extracted=False,
    vision_ocr_available=True,
  )
  assert infer_next_action(s) != "Run Google Vision OCR"
  assert infer_next_action(s) == "Extract sections from OCR text"


def test_sections_stale_when_pypdf_source(tmp_path: Path) -> None:
  ocr_dir = tmp_path / "ocr_pack"
  ocr_dir.mkdir()
  (ocr_dir / "publication_fulltext_raw.csv").write_text("pub,page\n", encoding="utf-8")
  sec_dir = tmp_path / "sec_pack"
  sec_dir.mkdir()
  stale = sections_stale_vs_ocr_output(
    {"source_raw_csv": str(tmp_path / "outputs/local_v8_pdf_text_extract/case/pypdf.csv")},
    sec_dir,
    ocr_dir,
  )
  assert stale is True


def test_sections_stale_when_ocr_newer(tmp_path: Path) -> None:
  ocr_dir = tmp_path / "ocr_pack"
  sec_dir = tmp_path / "sec_pack"
  ocr_dir.mkdir()
  sec_dir.mkdir()
  ocr_raw = ocr_dir / "publication_fulltext_raw.csv"
  ocr_raw.write_text("pub\n", encoding="utf-8")
  import os
  import time

  past = time.time() - 3600
  os.utime(sec_dir, (past, past))
  os.utime(ocr_dir, (time.time(), time.time()))
  stale = sections_stale_vs_ocr_output(
    {"source_raw_csv": str(ocr_raw)},
    sec_dir,
    ocr_dir,
  )
  assert stale is True


def test_find_publication_fulltext_raw_pack_prefers_ocr(tmp_path: Path) -> None:
  pypdf_dir = tmp_path / "outputs" / "local_v8_pdf_text_extract" / f"{CASE_ID}_pypdf"
  ocr_dir = tmp_path / "outputs" / "local_v8_google_vision_ocr" / f"{CASE_ID}_ocr"
  _write_ocr_raw_csv(ocr_dir / "publication_fulltext_raw.csv", pages=9, chars_per_page=10)
  pypdf_dir.mkdir(parents=True)
  with (pypdf_dir / "publication_fulltext_raw.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(
      handle,
      fieldnames=[
        "case_id", "publication_number", "source_file", "page_no", "text",
        "text_length", "extraction_method", "needs_ocr", "warning",
      ],
    )
    writer.writeheader()
    writer.writerow({
      "case_id": CASE_ID,
      "publication_number": PUB,
      "source_file": "",
      "page_no": 1,
      "text": "short",
      "text_length": 5,
      "extraction_method": "pypdf",
      "needs_ocr": True,
      "warning": "",
    })

  pack = find_publication_fulltext_raw_pack(
    CASE_ID, tmp_path, publication_number=PUB, prefer_ocr=True,
  )
  assert pack is not None
  assert pack.extraction_method == EXTRACTION_METHOD_VISION
  assert pack.total_rows == 9
  assert pack.total_text_length == 90


def test_ocr_ui_needs_sections_from_ocr() -> None:
  mod = importlib.import_module("tech_cartography.ui.v8_google_vision_ocr_ui")
  s = _status(
    vision_ocr_text_extracted=True,
    sections_extracted=True,
    sections_stale_vs_ocr=True,
  )
  assert mod._needs_sections_from_ocr(s) is True


def test_cli_script_importable() -> None:
  import importlib.util

  script = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_v8_section_extract_from_latest_ocr.py"
  )
  spec = importlib.util.spec_from_file_location("run_v8_section_extract_from_latest_ocr", script)
  assert spec and spec.loader
  mod = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(mod)
  assert hasattr(mod, "main")


def test_cli_dry_run_detects_ocr_csv(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
  import importlib.util

  ocr_dir = tmp_path / "outputs" / "local_v8_google_vision_ocr" / f"{CASE_ID}_ocr"
  _write_ocr_raw_csv(ocr_dir / "publication_fulltext_raw.csv", pages=9, chars_per_page=867)
  script = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_v8_section_extract_from_latest_ocr.py"
  )
  spec = importlib.util.spec_from_file_location("run_v8_section_extract_cli", script)
  assert spec and spec.loader
  mod = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(mod)

  pack = find_publication_fulltext_raw_pack(
    CASE_ID, tmp_path, publication_number=PUB, prefer_ocr=True,
  )
  assert pack is not None
  with patch.object(mod, "PROJECT_ROOT", tmp_path), patch.object(
    mod,
    "find_publication_fulltext_raw_pack",
    return_value=pack,
  ):
    with patch("sys.argv", [
      "run_v8_section_extract_from_latest_ocr.py",
      "--case-id", CASE_ID,
      "--publication-number", PUB,
      "--dry-run",
    ]):
      assert mod.main() == 0
  captured = capsys.readouterr().out
  assert "raw_csv_path:" in captured
  assert "dry-run" in captured
