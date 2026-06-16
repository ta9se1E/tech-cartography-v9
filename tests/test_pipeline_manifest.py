from __future__ import annotations

from pathlib import Path

from tech_cartography.orchestration.pipeline_config import PipelineConfig
from tech_cartography.orchestration.pipeline_manifest import (
  PipelineStageResult,
  create_manifest,
  load_manifest,
  save_manifest,
  summarize_manifest,
  update_stage_result,
)


def test_manifest_save_and_load(tmp_path: Path) -> None:
  cfg = PipelineConfig(theme="test", run_name="demo", output_root=str(tmp_path))
  manifest = create_manifest(cfg, run_id="RID", run_output_dir=str(tmp_path / "RID"))
  manifest = update_stage_result(
    manifest,
    PipelineStageResult(stage_id="search_strategy", stage_name="Search Strategy", status="success"),
  )
  path = save_manifest(manifest, tmp_path)
  loaded = load_manifest(path)
  assert loaded.run_id == "RID"
  assert loaded.stage_results[0].stage_id == "search_strategy"


def test_manifest_summary_counts(tmp_path: Path) -> None:
  cfg = PipelineConfig(theme="test", run_name="demo", output_root=str(tmp_path))
  manifest = create_manifest(cfg, run_id="RID", run_output_dir=str(tmp_path / "RID"))
  manifest = update_stage_result(
    manifest,
    PipelineStageResult(stage_id="s1", stage_name="s1", status="success"),
  )
  manifest = update_stage_result(
    manifest,
    PipelineStageResult(stage_id="s2", stage_name="s2", status="failed"),
  )
  summary = summarize_manifest(manifest)
  assert summary["stage_counts"]["success"] == 1
  assert summary["stage_counts"]["failed"] == 1

