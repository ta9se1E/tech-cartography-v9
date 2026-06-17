"""Tests for paper query quality evaluation (Phase 18D)."""

from __future__ import annotations

from tech_cartography.evidence.paper_query_quality import (
  evaluate_paper_query_candidates,
  render_paper_query_quality_report,
  save_paper_query_quality_artifacts,
)


def _sample_candidates() -> list[dict]:
  return [
    {"query": "PAN carbon fiber carbonization", "query_type": "material_process", "confidence": "medium"},
    {"query": "carbon fiber tensile strength modulus", "query_type": "property_condition", "confidence": "low"},
    {"query": "carbon fiber surface treatment sizing", "query_type": "surface_interface", "confidence": "medium"},
    {"query": "carbon fiber microstructure modulus", "query_type": "structure_property", "confidence": "medium"},
    {"query": "PAN carbon fiber manufacturing review", "query_type": "broad_background", "confidence": "low"},
  ]


def test_plan_ready_when_query_count_and_coverage_ok() -> None:
  summary = evaluate_paper_query_candidates(_sample_candidates())
  assert summary["query_count"] >= 5
  assert summary["plan_ready_for_openalex"] is True
  assert summary["has_material_process_query"] is True
  assert summary["has_property_query"] is True


def test_only_broad_background_not_ready() -> None:
  summary = evaluate_paper_query_candidates(
    [
      {"query": "carbon fiber review", "query_type": "broad_background", "confidence": "low"},
      {"query": "PAN review", "query_type": "broad_background", "confidence": "low"},
      {"query": "manufacturing review", "query_type": "broad_background", "confidence": "low"},
      {"query": "background review", "query_type": "broad_background", "confidence": "low"},
      {"query": "fiber review", "query_type": "broad_background", "confidence": "low"},
    ],
  )
  assert summary["only_broad_background"] is True
  assert summary["plan_ready_for_openalex"] is False


def test_duplicate_count_reported() -> None:
  rows = _sample_candidates() + [_sample_candidates()[0]]
  summary = evaluate_paper_query_candidates(rows)
  assert summary["duplicate_count"] >= 1


def test_confidence_distribution_reported() -> None:
  summary = evaluate_paper_query_candidates(_sample_candidates())
  assert summary["confidence_distribution"].get("medium", 0) >= 1
  assert summary["confidence_distribution"].get("low", 0) >= 1


def test_quality_report_artifacts(tmp_path) -> None:
  rows = _sample_candidates()
  paths = save_paper_query_quality_artifacts(rows, tmp_path)
  assert paths["paper_query_quality_summary_json"]
  assert paths["paper_query_quality_report_md"]
  md = render_paper_query_quality_report(rows)
  assert "Paper Query Quality Report" in md
  assert "usd" not in md.lower()
