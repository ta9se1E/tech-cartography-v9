"""Quality tests for Phase27N.5 One Case Demo E2E."""

from __future__ import annotations

import json
import re
from pathlib import Path

from tech_cartography.runtime.v8_one_case_demo_schema import DEFAULT_ONE_CASE_INPUT_CSV
from tech_cartography.services.v8_one_case_demo_e2e import (
  OneCaseDemoRunOptions,
  assess_one_case_demo_status,
  run_one_case_demo_e2e,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_schema_json_serializable() -> None:
  summary = assess_one_case_demo_status(project_root=PROJECT_ROOT)
  blob = json.dumps(summary.to_dict())
  parsed = json.loads(blob)
  assert parsed["no_cloud_build"] is True
  assert parsed["no_cloud_run_deploy"] is True


def test_missing_csv_next_action_mentions_path() -> None:
  csv_path = PROJECT_ROOT / DEFAULT_ONE_CASE_INPUT_CSV
  if csv_path.is_file():
    return
  summary = assess_one_case_demo_status(project_root=PROJECT_ROOT)
  assert summary.input_csv_exists is False
  assert "case_01_bigquery_export_1000.csv" in summary.next_user_action
  assert summary.overall_status == "needs_input_csv"


def test_manual_claim_guidance_when_top5_without_claim() -> None:
  summary = assess_one_case_demo_status(project_root=PROJECT_ROOT)
  if not summary.top5_publication_numbers or summary.manual_claim_count >= 1:
    return
  if summary.overall_status == "needs_input_csv":
    return
  assert "Claim Map" in summary.next_user_action
  assert "手動投入" in summary.next_user_action


def test_runbook_mentions_no_generated_claim() -> None:
  text = (PROJECT_ROOT / "docs/one_case_real_demo_runbook.md").read_text(encoding="utf-8")
  assert "自動生成" in text
  assert "fixture" in text.lower() or "架空" in text


def test_runbook_mentions_real_csv() -> None:
  text = (PROJECT_ROOT / "docs/one_case_real_demo_runbook.md").read_text(encoding="utf-8")
  assert "case_01_bigquery_export_1000.csv" in text


def test_e2e_service_no_gcloud() -> None:
  text = (PROJECT_ROOT / "scripts/run_v8_one_case_demo_e2e_check.py").read_text(encoding="utf-8")
  assert "gcloud" not in text


def test_e2e_options_no_external_api() -> None:
  service_text = (
    PROJECT_ROOT / "src/tech_cartography/services/v8_one_case_demo_e2e.py"
  ).read_text(encoding="utf-8")
  assert "requests.get" not in service_text
  assert "openalex" not in service_text.lower()


def test_missing_csv_run_exit_code_1() -> None:
  csv_path = PROJECT_ROOT / DEFAULT_ONE_CASE_INPUT_CSV
  if csv_path.is_file():
    return
  _, code = run_one_case_demo_e2e(
    OneCaseDemoRunOptions(project_root=PROJECT_ROOT),
  )
  assert code == 1
