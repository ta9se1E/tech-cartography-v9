"""Quality tests for v8 large candidate (Phase 27J.0)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tech_cartography.services.v8_large_candidate_import import import_large_candidates
from tech_cartography.services.v8_large_candidate_shortlist import build_staged_shortlist
from tech_cartography.ui.v8_text_rendering import normalize_text_items

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "v8_large_candidate_fixture.csv"
CASE_ID = "case_01_pan_graphitization"
SECRET_RE = re.compile(r"(smtp_password|tavily_api_key|eyJhbGci)", re.IGNORECASE)


@pytest.fixture
def pack(tmp_path: Path):
  (tmp_path / "cases" / CASE_ID).mkdir(parents=True)
  import_large_candidates(case_id=CASE_ID, input_path=FIXTURE, project_root=tmp_path)
  return build_staged_shortlist(CASE_ID, project_root=tmp_path)


def test_manifest_no_secrets(pack) -> None:
  text = Path(pack.manifest_path).read_text(encoding="utf-8")
  assert not SECRET_RE.search(text)
  manifest = json.loads(text)
  assert manifest["case_id"] == CASE_ID


def test_no_fake_urls_in_import(tmp_path: Path) -> None:
  (tmp_path / "cases" / CASE_ID).mkdir(parents=True)
  result = import_large_candidates(case_id=CASE_ID, input_path=FIXTURE, project_root=tmp_path)
  from tech_cartography.services.v8_large_candidate_import import load_large_candidates_csv
  records = load_large_candidates_csv(Path(result.output_candidates_path))
  for r in records:
    assert "fake-doi" not in r.url.lower()
    assert "example.com" not in r.url.lower()


def test_japanese_text_guard() -> None:
  sample = "入力タブで1000件候補CSVを取り込んでください。"
  assert len(normalize_text_items(sample)) == 1


def test_cases_dir_no_large_csv() -> None:
  root = Path(__file__).resolve().parents[1]
  for case_id in (
    "case_01_pan_graphitization",
    "case_02_sizing_interface",
    "case_03_pressure_vessel_filament_winding",
  ):
    large = root / "cases" / case_id / "source_candidates_large.csv"
    assert not large.exists(), f"cases/ should not contain pre-populated {large}"
