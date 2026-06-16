from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.orchestration.latest_outputs import (
  build_artifact_index,
  read_latest_run_pointer,
  render_artifact_index_markdown,
  save_artifact_index,
  write_latest_run_pointer,
)
from tech_cartography.orchestration.pipeline_config import PipelineConfig
from tech_cartography.orchestration.pipeline_manifest import (
  PipelineStageResult,
  create_manifest,
  update_stage_result,
)


def test_latest_run_pointer_write_and_read(tmp_path: Path, monkeypatch) -> None:
  # Ensure pointer is written under outputs/
  monkeypatch.chdir(tmp_path)
  (tmp_path / "outputs").mkdir()
  (tmp_path / "outputs" / "pipeline_runs").mkdir(parents=True)
  pointer_path = write_latest_run_pointer("RID", "outputs/pipeline_runs/RID/run_manifest.json", "outputs/pipeline_runs")
  assert Path(pointer_path).exists()
  payload = read_latest_run_pointer("outputs/pipeline_runs")
  assert payload and payload["run_id"] == "RID"


def test_artifact_index_markdown_contains_outputs(tmp_path: Path) -> None:
  cfg = PipelineConfig(theme="test", run_name="demo", output_root=str(tmp_path))
  manifest = create_manifest(cfg, run_id="RID", run_output_dir=str(tmp_path / "RID"))
  manifest = update_stage_result(
    manifest,
    PipelineStageResult(
      stage_id="synthesis_report",
      stage_name="Synthesis",
      status="success",
      output_paths={"carbon_fiber_evidence_map_md": "outputs/x.md"},
    ),
  )
  manifest.final_outputs["final_report_md"] = "outputs/x.md"
  index = build_artifact_index(
    manifest,
    {
      "ranked_patents_csv": "outputs/x.csv",
      "strategic_watch_candidates_csv": "outputs/watch.csv",
    },
  )
  md = render_artifact_index_markdown(index)
  assert "final_report_md" in md
  assert "strategic_watch_candidates_csv" in md
  path = save_artifact_index(index, str(tmp_path))
  assert Path(path).exists()
  assert (tmp_path / "artifact_index.json").exists()
  _ = json.loads((tmp_path / "artifact_index.json").read_text(encoding="utf-8"))

