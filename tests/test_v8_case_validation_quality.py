"""Quality tests for v8 three case validation pack (Phase 27I)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from tech_cartography.services.v8_case_validation_export import export_validation_pack, pack_to_markdown
from tech_cartography.services.v8_case_validation_pack import build_three_case_validation_pack
from tech_cartography.services.v8_sources_table import project_root_from_here
from tech_cartography.ui.v8_text_rendering import normalize_text_items

CASE_IDS = (
  "case_01_pan_graphitization",
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
)

LEGAL_FORBIDDEN = re.compile(r"\b(FTO|侵害|有効性)\b")
SECRET_RE = re.compile(r"(smtp_password|tavily_api_key|eyJhbGci)", re.IGNORECASE)


def test_pack_has_safety_notices_and_no_legal_judgement_claims() -> None:
  root = project_root_from_here()
  pack = build_three_case_validation_pack(project_root=root, ensure_artifacts=False)
  md = pack_to_markdown(pack)
  assert pack.no_legal_judgement is True
  assert "証明" in md or "proof" in md.lower() or "FTO" in md
  assert not SECRET_RE.search(md)


def test_all_cases_needs_claim_text_or_warning_when_empty_claims() -> None:
  root = project_root_from_here()
  pack = build_three_case_validation_pack(project_root=root, ensure_artifacts=False)
  for report in pack.cases:
    assert report.readiness_for_demo in {
      "ready",
      "needs_claim_text",
      "needs_more_sources",
      "needs_manual_review",
      "not_ready",
    }
  readiness_values = {r.readiness_for_demo for r in pack.cases}
  assert "needs_claim_text" in readiness_values or pack.overall_status == "warning"


def test_fixed_point_step_preserves_email_scheduler_plans() -> None:
  root = project_root_from_here()
  pack = build_three_case_validation_pack(project_root=root, ensure_artifacts=False)
  for report in pack.cases:
    fp = next(s for s in report.step_results if s.step_id == "fixed_point_observation")
    assert fp.status != "fail"
    assert report.no_email_send is True
    assert report.no_scheduler_start is True


def test_export_manifest_has_no_secrets() -> None:
  root = project_root_from_here()
  pack = build_three_case_validation_pack(project_root=root, ensure_artifacts=False)
  result = export_validation_pack(pack, project_root=root)
  manifest_text = Path(result.manifest_path).read_text(encoding="utf-8")
  assert not SECRET_RE.search(manifest_text)
  manifest = json.loads(manifest_text)
  assert manifest["common_blocking_issues"]
  assert manifest["common_next_actions"]


def test_japanese_text_rendering_guard() -> None:
  sample = "次は「Export」タブで3案件検証パックを作成してください。"
  items = normalize_text_items(sample)
  assert len(items) == 1
  assert items[0] == sample


def test_common_blocking_and_actions_not_empty() -> None:
  root = project_root_from_here()
  pack = build_three_case_validation_pack(project_root=root, ensure_artifacts=False)
  assert pack.common_blocking_issues
  assert pack.common_next_actions
  assert "Cloud" in pack.cloud_readiness_summary
  assert "Demo" in pack.demo_readiness_summary or "readiness" in pack.demo_readiness_summary.lower()
