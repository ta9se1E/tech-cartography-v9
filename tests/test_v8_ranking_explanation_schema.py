"""Tests for v8 ranking explanation schema (Phase 27J.1)."""

from __future__ import annotations

import json

from tech_cartography.runtime.v8_ranking_explanation_schema import (
  V8CandidateRankingExplanation,
  V8RankingExplanationReport,
  V8ScoreContribution,
)


def test_score_contribution_json_serializable() -> None:
  c = V8ScoreContribution(
    contribution_id="c1:contrib:include_term_hit:0",
    factor_name="include_term_hit",
    matched_value="carbonization",
    score_delta=2.0,
    reason="include term matched",
    evidence_field="title",
  )
  payload = json.dumps(c.to_dict())
  assert "carbonization" in payload


def test_candidate_ranking_explanation_json_serializable() -> None:
  exp = V8CandidateRankingExplanation(
    candidate_id="c1",
    case_id="case_01_pan_graphitization",
    publication_number="US5176959",
    why_selected="test fixture only",
    positive_reasons=["include term hit"],
    negative_reasons=[],
    ranking_policy="patent_triage_adapter",
    no_legal_judgement=True,
  )
  payload = json.dumps(exp.to_dict())
  assert "why_selected" in payload
  assert exp.no_legal_judgement is True


def test_ranking_report_json_serializable() -> None:
  report = V8RankingExplanationReport(
    report_id="r1",
    case_id="case_01",
    generated_at="2026-01-01T00:00:00Z",
    triage_engine="patent_triage",
    no_deep_dive_all_population=True,
  )
  payload = json.dumps(report.to_dict())
  assert "no_deep_dive_all_population" in payload
