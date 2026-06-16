from __future__ import annotations

from tech_cartography.orchestration.pipeline_config import PipelineConfig
from tech_cartography.orchestration.stage_resolver import (
  resolve_stage_order,
  should_run_stage,
  validate_stage_inputs,
)


def test_stage_order_phase_1_to_11() -> None:
  order = resolve_stage_order()
  assert order[0] == "search_strategy"
  assert order[-1] == "synthesis_report"
  assert order.index("business_view_agent") > order.index("web_signal_mapping")


def test_skip_stage_disables() -> None:
  cfg = PipelineConfig(skip_stages=["openalex_paper_evidence"])
  assert should_run_stage("openalex_paper_evidence", cfg) is False
  assert should_run_stage("search_strategy", cfg) is True


def test_start_stop_stage_range() -> None:
  cfg = PipelineConfig(start_stage="technology_clustering_ranking", stop_stage="business_view_agent")
  assert should_run_stage("search_strategy", cfg) is False
  assert should_run_stage("technology_clustering_ranking", cfg) is True
  assert should_run_stage("business_view_agent", cfg) is True
  assert should_run_stage("synthesis_report", cfg) is False


def test_validate_stage_inputs_detects_missing() -> None:
  res = validate_stage_inputs("synthesis_report", {"cluster_summary_json": "missing.json"})
  assert res["ok"] is False
  assert "top20_patents_csv" in res["missing"]

