"""Tests for Phase27S.0 Google Patents link provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.services.v8_google_patents_links import (
  build_google_patents_search_url,
  build_google_patents_url,
  build_top5_google_patents_links,
  export_google_patents_links,
  links_to_csv_text,
  normalize_publication_number,
  resolve_pdf_upload_status,
  save_patent_pdf_upload,
)
from tech_cartography.services.v8_sources_table import project_root_from_here

CASE_ID = "case_01_pan_graphitization"
CN_TOP5 = (
  "CN108286090A",
  "CN117987966A",
  "CN105401262A",
  "CN105506785B",
  "CN109402791B",
)


def test_normalize_publication_number() -> None:
  assert normalize_publication_number("cn108286090a") == "CN108286090A"
  assert normalize_publication_number("CN-108286090-A") == "CN108286090A"


def test_build_google_patents_url_format() -> None:
  url = build_google_patents_url("CN108286090A")
  assert url == "https://patents.google.com/patent/CN108286090A/en"
  assert ".pdf" not in url.lower()
  assert "storage.googleapis" not in url


def test_build_google_patents_search_url() -> None:
  url = build_google_patents_search_url("CN108286090A")
  assert "patents.google.com" in url
  assert "CN108286090A" in url


@pytest.mark.parametrize("pub", CN_TOP5)
def test_top5_url_examples(pub: str) -> None:
  assert build_google_patents_url(pub) == f"https://patents.google.com/patent/{pub}/en"


def test_build_top5_google_patents_links() -> None:
  root = project_root_from_here()
  links = build_top5_google_patents_links(CASE_ID, root)
  if not links:
    pytest.skip("Top5 artifact not available")
  assert len(links) == 5
  for link in links:
    assert link.google_patents_url.startswith("https://patents.google.com/patent/")
    assert link.google_patents_url.endswith("/en")
    assert ".pdf" not in link.google_patents_url.lower()
    assert link.pdf_upload_status in {"未アップロード", "アップロード済み"}


def test_export_google_patents_links(tmp_path: Path) -> None:
  from tech_cartography.runtime.v8_google_patents_links_schema import GooglePatentsLink

  links = [
    GooglePatentsLink(
      case_id=CASE_ID,
      publication_number="CN108286090A",
      title="Test",
      google_patents_url="https://patents.google.com/patent/CN108286090A/en",
    )
  ]
  export = export_google_patents_links(links, project_root=tmp_path)
  assert Path(export.csv_path).exists()
  assert Path(export.md_path).exists()
  csv_text = links_to_csv_text(links)
  assert "google_patents_url" in csv_text
  assert ".pdf" not in csv_text.split("google_patents_url")[1][:80]


def test_pdf_upload_status(tmp_path: Path) -> None:
  pub = "CN108286090A"
  assert resolve_pdf_upload_status(pub, case_id=CASE_ID, project_root=tmp_path) == "未アップロード"
  save_patent_pdf_upload(
    case_id=CASE_ID,
    publication_number=pub,
    pdf_bytes=b"%PDF-1.4 test",
    original_filename="test.pdf",
    project_root=tmp_path,
  )
  assert resolve_pdf_upload_status(pub, case_id=CASE_ID, project_root=tmp_path) == "アップロード済み"


def test_ui_modules_reference_google_patents() -> None:
  """Phase27S.4.1: Google Patents links live in Top5 Deep Dive, not input tab."""
  deep_dive = Path("src/tech_cartography/ui/v8_top5_pdf_deep_dive_ui.py").read_text(encoding="utf-8")
  assert "Google Patents" in deep_dive or "google_patents" in deep_dive
  shortlist = Path("src/tech_cartography/ui/v8_patent_shortlist_ui.py").read_text(encoding="utf-8")
  assert "render_top5_pdf_deep_dive_section" in shortlist
  gap_text = Path("src/tech_cartography/ui/v8_gap_next_actions_ui.py").read_text(encoding="utf-8")
  assert "Top5 Deep Dive" in gap_text
