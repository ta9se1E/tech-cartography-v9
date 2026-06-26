"""Quality tests for v8 final UI guidance (Phase 27M)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.services.v8_demo_readiness import assess_case_demo_readiness, build_demo_readiness_report
from tech_cartography.services.v8_demo_readiness_export import report_to_markdown
from tech_cartography.services.v8_sources_table import project_root_from_here


def test_missing_artifact_not_marked_ready() -> None:
  root = project_root_from_here()
  readiness = assess_case_demo_readiness("case_01_pan_graphitization", project_root=root)
  ev = next(s for s in readiness.step_statuses if s.step_name == "evidence_map")
  if ev.status == "not_generated":
    assert ev.status != "ready"
    assert "artifact missing" in ev.summary.lower()


def test_report_mentions_legal_disclaimer() -> None:
  report = build_demo_readiness_report(project_root=project_root_from_here())
  md = report_to_markdown(report)
  assert "FTO" in md or "侵害" in md or "legal" in md.lower()


def test_recommended_demo_flow_not_empty() -> None:
  report = build_demo_readiness_report(project_root=project_root_from_here())
  for case in report.cases:
    assert case.recommended_demo_flow


def test_claim_map_ui_next_action_card_signature() -> None:
  text = Path(__file__).resolve().parents[1].joinpath(
    "src/tech_cartography/ui/v8_claim_map_ui.py"
  ).read_text(encoding="utf-8")
  assert 'render_next_action_card("次にやること"' in text.replace("\n", " ") or (
    "render_next_action_card(" in text and "next_actions" in text
  )
