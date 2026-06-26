"""Quality tests for v8 Gap / Next Actions (Phase 27G)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.runtime.v8_gap_next_actions_schema import GAP_NEXT_ACTIONS_SAFETY_NOTICES
from tech_cartography.services.v8_gap_next_actions import build_gap_next_actions_report
from tech_cartography.services.v8_gap_next_actions_export import export_gap_next_actions, gap_next_actions_to_markdown
from tech_cartography.services.v8_sources_repository import project_root_from_here

CASE_IDS = (
  "case_01_pan_graphitization",
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
)


def test_three_cases_top_3_actions() -> None:
  root = project_root_from_here()
  for case_id in CASE_IDS:
    report = build_gap_next_actions_report(case_id=case_id, project_root=root)
    assert len(report.top_3_actions) <= 3
    assert len(report.top_3_actions) >= 1
    for action in report.top_3_actions:
      assert action.action_title.strip()
      assert action.no_legal_judgement is True


def test_markdown_safety_notices() -> None:
  root = project_root_from_here()
  report = build_gap_next_actions_report(case_id="case_01_pan_graphitization", project_root=root)
  md = gap_next_actions_to_markdown(report)
  for notice in GAP_NEXT_ACTIONS_SAFETY_NOTICES[:3]:
    assert any(part in md for part in notice.split("—")[0].split("、")[:1])


def test_no_legal_judgement_in_export(tmp_path: Path) -> None:
  root = project_root_from_here()
  report = build_gap_next_actions_report(case_id="case_02_sizing_interface", project_root=root)
  result = export_gap_next_actions(report, project_root=tmp_path)
  md = Path(result.md_path).read_text(encoding="utf-8")
  assert "侵害" in md or "FTO" in md
  assert "法的" in md


def test_mail_scheduler_not_removed() -> None:
  fixed_point = Path("src/tech_cartography/ui/v8_fixed_point_observation_ui.py").read_text(encoding="utf-8")
  gap_ui = Path("src/tech_cartography/ui/v8_gap_next_actions_ui.py").read_text(encoding="utf-8")
  assert "メール送信" in fixed_point
  assert "Scheduler" in fixed_point
  assert "メール" in gap_ui or "Scheduler" in gap_ui
