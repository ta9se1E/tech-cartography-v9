"""Tests for v8 case profiles and source candidates (Phase27A)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_IDS = (
  "case_01_pan_graphitization",
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
)

REQUIRED_PROFILE_KEYS = (
  "case_id",
  "case_name",
  "theme",
  "target_user",
  "target_materials",
  "target_processes",
  "target_properties",
  "target_applications",
  "seed_keywords",
  "seed_queries",
  "seed_patent_ids",
  "expected_claim_axes",
  "expected_evidence_types",
  "watch_profile_update_policy",
  "fixed_point_observation_policy",
  "email_digest_policy",
  "scheduler_policy",
  "exclusion_keywords",
  "safety_policy",
)

CSV_COLUMNS = (
  "type",
  "title",
  "organization",
  "year",
  "url",
  "publication_number",
  "source_status",
  "evidence_role",
  "case_id",
  "notes",
)


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_case_profile_yaml_readable(case_id: str) -> None:
  path = PROJECT_ROOT / "cases" / case_id / "case_profile.yaml"
  data = yaml.safe_load(path.read_text(encoding="utf-8"))
  assert isinstance(data, dict)
  assert data["case_id"] == case_id
  for key in REQUIRED_PROFILE_KEYS:
    assert key in data, f"{case_id} missing key: {key}"


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_case_safety_policy(case_id: str) -> None:
  path = PROJECT_ROOT / "cases" / case_id / "case_profile.yaml"
  data = yaml.safe_load(path.read_text(encoding="utf-8"))
  safety = data["safety_policy"]
  assert safety["no_fto_judgement"] is True
  assert safety["no_fake_evidence"] is True
  assert safety["web_signal_is_candidate_only"] is True


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_source_candidates_csv_columns(case_id: str) -> None:
  path = PROJECT_ROOT / "cases" / case_id / "source_candidates.csv"
  with path.open(encoding="utf-8", newline="") as handle:
    reader = csv.DictReader(handle)
    assert reader.fieldnames is not None
    for col in CSV_COLUMNS:
      assert col in reader.fieldnames, f"{case_id} missing column: {col}"
    rows = list(reader)
  assert len(rows) >= 3, f"{case_id} needs at least 3 source rows"


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_validation_checklist_exists(case_id: str) -> None:
  path = PROJECT_ROOT / "cases" / case_id / "validation_checklist.md"
  text = path.read_text(encoding="utf-8")
  for item in (
    "Sources一覧",
    "Claim Map",
    "Evidence Gap",
    "Next Verification Actions",
    "Scheduler",
    "メール",
    "Export",
    "架空情報",
    "FTO",
  ):
    assert item in text


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_expected_outputs_covers_required_sections(case_id: str) -> None:
  path = PROJECT_ROOT / "cases" / case_id / "expected_outputs.md"
  text = path.read_text(encoding="utf-8")
  for section in (
    "Sources一覧",
    "読むべき特許",
    "Claim Map",
    "Evidence Map",
    "Evidence Gap",
    "Next Verification Actions",
    "定点観測",
    "Export",
  ):
    assert section in text
