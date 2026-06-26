"""Tests for v8 demo polish schema (Phase 27L)."""

from __future__ import annotations

import json

from tech_cartography.runtime.v8_demo_polish_schema import (
  DEMO_POLISH_SAFETY_NOTICES,
  V8DemoPolishReport,
  V8DemoStoryCard,
  V8EvidenceDemoStatus,
  V8GapDemoStatus,
)


def test_demo_polish_report_json_serializable() -> None:
  report = V8DemoPolishReport(
    report_id="case_01:demo:abc",
    case_id="case_01_pan_graphitization",
    publication_number="US5176959",
    generated_at="2026-06-27T00:00:00Z",
    evidence_demo_status=V8EvidenceDemoStatus(
      status_id="s1",
      case_id="case_01_pan_graphitization",
      publication_number="US5176959",
      claim_text_status="not_loaded",
      claim_text_required_count=5,
      evidence_map_not_proof=True,
    ),
    gap_demo_status=V8GapDemoStatus(
      status_id="g1",
      case_id="case_01_pan_graphitization",
      publication_number="US5176959",
      gap_count=5,
      top_3_next_actions=["load claim text"],
      gap_is_not_invalidity=True,
    ),
    story_cards=[
      V8DemoStoryCard(
        card_id="c1",
        case_id="case_01_pan_graphitization",
        card_title="test",
        card_type="caveat",
        key_message="Evidence Map is not proof",
      ),
    ],
    demo_narrative="demo narrative",
    no_email_send=True,
    no_scheduler_start=True,
  )
  payload = json.dumps(report.to_dict())
  restored = json.loads(payload)
  assert restored["case_id"] == "case_01_pan_graphitization"
  assert restored["evidence_demo_status"]["claim_text_required_count"] == 5
  assert "Evidence Map is not proof" in DEMO_POLISH_SAFETY_NOTICES[0]
