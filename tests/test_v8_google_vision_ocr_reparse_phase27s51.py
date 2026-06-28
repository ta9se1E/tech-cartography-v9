"""Tests for Phase27S.5.1 Vision OCR JSON aggregation / reparse."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tech_cartography.runtime.v8_google_vision_ocr_schema import (
  EXTRACTION_METHOD_VISION,
  OCR_HUMAN_REVIEW_WARNING,
)
from tech_cartography.services.v8_google_vision_ocr import (
  parse_vision_ocr_json_outputs,
  reparse_existing_vision_ocr_output,
  sort_vision_ocr_json_paths,
  write_vision_ocr_outputs,
)

CASE_ID = "test_case_ocr_s51"
PUB = "CN108286090A"


def _write_json(path: Path, page_text: str) -> None:
  path.write_text(
    json.dumps({"responses": [{"fullTextAnnotation": {"text": page_text}}]}),
    encoding="utf-8",
  )


def test_natural_sort_json_paths() -> None:
  paths = [
    Path("output-10-to-10.json"),
    Path("output-1-to-1.json"),
    Path("output-2-to-2.json"),
  ]
  sorted_paths = sort_vision_ocr_json_paths(paths)
  assert [p.name for p in sorted_paths] == [
    "output-1-to-1.json",
    "output-2-to-2.json",
    "output-10-to-10.json",
  ]


def test_parse_multiple_json_all_responses(tmp_path: Path) -> None:
  json_dir = tmp_path / "raw_vision_json"
  json_dir.mkdir()
  texts = {1: "page one", 2: "page two", 10: "page ten"}
  for page_no, text in texts.items():
    _write_json(json_dir / f"output-{page_no}-to-{page_no}.json", text)

  pdf_path = tmp_path / f"{PUB}.pdf"
  pdf_path.write_bytes(b"%PDF")
  result = parse_vision_ocr_json_outputs(
    list(json_dir.glob("*.json")), CASE_ID, PUB, pdf_path,
  )

  assert result.page_count == 3
  assert result.extracted_pages == 3
  assert result.total_text_length == sum(len(t) for t in texts.values())
  assert [p.page_no for p in result.pages] == [1, 2, 10]
  assert result.status == "ocr_completed"


def test_publication_fulltext_raw_all_pages(tmp_path: Path) -> None:
  json_dir = tmp_path / "raw_vision_json"
  json_dir.mkdir()
  for i in range(1, 4):
    _write_json(json_dir / f"output-{i}-to-{i}.json", f"text page {i}" * 10)

  pdf_path = tmp_path / f"{PUB}.pdf"
  pdf_path.write_bytes(b"%PDF")
  result = parse_vision_ocr_json_outputs(
    list(json_dir.glob("*.json")), CASE_ID, PUB, pdf_path,
  )
  out_dir = write_vision_ocr_outputs(CASE_ID, [result], tmp_path / "outputs", pack_dir=tmp_path / "pack")

  raw_csv = out_dir / "publication_fulltext_raw.csv"
  with raw_csv.open(encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))

  assert len(rows) == 3
  assert sum(int(r["text_length"]) for r in rows) == result.total_text_length
  assert all(r["extraction_method"] == EXTRACTION_METHOD_VISION for r in rows)
  assert all(r["needs_ocr"] == "False" for r in rows)
  assert all(OCR_HUMAN_REVIEW_WARNING in r["warning"] for r in rows)


def test_summary_counts(tmp_path: Path) -> None:
  json_dir = tmp_path / "raw_vision_json"
  json_dir.mkdir()
  _write_json(json_dir / "output-1-to-1.json", "alpha")
  _write_json(json_dir / "output-2-to-2.json", "")

  pdf_path = tmp_path / f"{PUB}.pdf"
  result = parse_vision_ocr_json_outputs(
    list(json_dir.glob("*.json")), CASE_ID, PUB, pdf_path,
  )
  out_dir = write_vision_ocr_outputs(CASE_ID, [result], tmp_path / "outputs", pack_dir=tmp_path / "pack2")

  with (out_dir / "google_vision_ocr_summary.csv").open(encoding="utf-8", newline="") as handle:
    row = next(csv.DictReader(handle))

  assert int(row["page_count"]) == 2
  assert int(row["extracted_pages"]) == 1
  assert int(row["total_text_length"]) == 5
  assert row["status"] == "ocr_completed"


def test_reparse_existing_without_live_api(tmp_path: Path) -> None:
  pack = tmp_path / "outputs" / "local_v8_google_vision_ocr" / f"{CASE_ID}_test"
  json_dir = pack / "raw_vision_json"
  json_dir.mkdir(parents=True)
  _write_json(json_dir / "output-1-to-1.json", "reparse one")
  _write_json(json_dir / "output-2-to-2.json", "reparse two")

  summary_csv = pack / "google_vision_ocr_summary.csv"
  with summary_csv.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=[
      "publication_number", "source_pdf_path", "gcs_input_uri", "gcs_output_uri",
    ])
    writer.writeheader()
    writer.writerow({
      "publication_number": PUB,
      "source_pdf_path": str(tmp_path / f"{PUB}.pdf"),
      "gcs_input_uri": "gs://bucket/in.pdf",
      "gcs_output_uri": "gs://bucket/out/",
    })

  (tmp_path / f"{PUB}.pdf").write_bytes(b"%PDF")
  project_root = tmp_path

  with patch("tech_cartography.services.v8_google_vision_ocr.run_google_vision_ocr_for_pdf") as live:
    result = reparse_existing_vision_ocr_output(
      pack, CASE_ID, PUB, project_root=project_root,
    )
    live.assert_not_called()

  assert result.extracted_pages == 2
  assert result.total_text_length > 0
  raw_csv = pack / "publication_fulltext_raw.csv"
  assert raw_csv.exists()
  with raw_csv.open(encoding="utf-8", newline="") as handle:
    assert len(list(csv.DictReader(handle))) == 2


def test_needs_human_review_and_warning(tmp_path: Path) -> None:
  json_dir = tmp_path / "raw"
  json_dir.mkdir()
  _write_json(json_dir / "output-1-to-1.json", "human review required text")
  result = parse_vision_ocr_json_outputs(
    list(json_dir.glob("*.json")), CASE_ID, PUB, tmp_path / "x.pdf",
  )
  assert result.needs_human_review is True
  assert OCR_HUMAN_REVIEW_WARNING in (result.warning or "")
