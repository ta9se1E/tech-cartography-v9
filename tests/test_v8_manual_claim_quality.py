"""Quality tests for v8 manual claim injection (Phase 27J)."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from tech_cartography.services.v8_claim_map import build_claim_map
from tech_cartography.services.v8_evidence_map import build_evidence_map
from tech_cartography.services.v8_manual_claim_injection import inject_manual_claim
from tech_cartography.services.v8_manual_claim_refresh import refresh_after_manual_claim
from tech_cartography.services.v8_manual_claim_refresh_export import export_manual_claim_refresh, report_to_markdown
from tech_cartography.services.v8_sources_table import project_root_from_here
from tech_cartography.ui.v8_text_rendering import normalize_text_items

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "v8_manual_claim_fixture.txt"
CASE_ID = "case_01_pan_graphitization"
PUB = "US5176959"
SECRET_RE = re.compile(r"(smtp_password|tavily_api_key|eyJhbGci)", re.IGNORECASE)


@pytest.fixture
def injected_case_root(tmp_path: Path) -> Path:
  root = project_root_from_here()
  case_dst = tmp_path / "cases" / CASE_ID
  case_dst.mkdir(parents=True)
  for name in ("claims_input.csv", "source_candidates.csv", "case_profile.yaml"):
    src = root / "cases" / CASE_ID / name
    if src.exists():
      shutil.copy(src, case_dst / name)
  inject_manual_claim(
    case_id=CASE_ID,
    publication_number=PUB,
    claim_no="1",
    claim_text=FIXTURE_PATH.read_text(encoding="utf-8").strip(),
    project_root=tmp_path,
  )
  return tmp_path


def test_cases_dir_has_no_fabricated_claim_text() -> None:
  import csv

  root = project_root_from_here()
  for case_id in (
    "case_01_pan_graphitization",
    "case_02_sizing_interface",
    "case_03_pressure_vessel_filament_winding",
  ):
    csv_path = root / "cases" / case_id / "claims_input.csv"
    with csv_path.open(encoding="utf-8", newline="") as handle:
      rows = list(csv.DictReader(handle))
    for row in rows:
      assert not str(row.get("claim_text") or "").strip(), (
        f"{case_id} should not have claim_text in cases/"
      )


def test_evidence_map_keeps_candidate_treatment(injected_case_root: Path) -> None:
  emap = build_evidence_map(case_id=CASE_ID, project_root=injected_case_root)
  web_company = [
    l for l in emap.links
    if l.source_type in {"web", "company"}
    or l.support_type in {"web_signal_candidate", "company_signal_candidate"}
  ]
  for link in web_company:
    assert link.candidate_information_only or link.human_review_required


def test_no_secrets_in_refresh_export(injected_case_root: Path) -> None:
  report = refresh_after_manual_claim(
    case_id=CASE_ID,
    publication_number=PUB,
    project_root=injected_case_root,
  )
  md = report_to_markdown(report)
  assert not SECRET_RE.search(md)
  export_result = export_manual_claim_refresh(report, project_root=injected_case_root)
  manifest = json.loads(Path(export_result.manifest_path).read_text(encoding="utf-8"))
  assert not SECRET_RE.search(json.dumps(manifest))


def test_claim_map_does_not_fabricate_claims(injected_case_root: Path) -> None:
  claim_map = build_claim_map(case_id=CASE_ID, project_root=injected_case_root)
  not_loaded = [r for r in claim_map.records if r.claim_text_status == "not_loaded"]
  for rec in not_loaded:
    assert rec.claim_text == "claim text not loaded"


def test_japanese_text_rendering_guard() -> None:
  sample = "「Claim Map」タブで実 claim 本文を手動投入してください。"
  items = normalize_text_items(sample)
  assert len(items) == 1


def test_fixture_file_has_disclaimer() -> None:
  text = FIXTURE_PATH.read_text(encoding="utf-8")
  assert "test fixture only, not real patent claim" in text
