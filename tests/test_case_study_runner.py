from __future__ import annotations

from pathlib import Path

import tech_cartography.orchestration.case_study_runner as runner
from tech_cartography.orchestration.pipeline_config import PipelineConfig


def test_pipeline_runner_creates_manifest_with_mock_stages(tmp_path: Path, monkeypatch) -> None:
  monkeypatch.chdir(tmp_path)
  (tmp_path / "outputs").mkdir()

  cfg = PipelineConfig(
    theme="test",
    run_name="demo",
    output_root="outputs/pipeline_runs",
    web_signal_file="case_studies/carbon_fiber/web_signals/x.csv",
    use_cache=True,
  )

  called: list[str] = []

  def _ok(stage_key: str):
    def _fn(_cfg, out_dir: str, _prev):
      called.append(stage_key)
      Path(out_dir).mkdir(parents=True, exist_ok=True)
      return {"status": "ok", "paths": {f"{stage_key}_out": str(Path(out_dir) / "x.txt")}, "summary": {"k": stage_key}}

    return _fn

  def _fail(_cfg, out_dir: str, _prev):
    called.append("fail_stage")
    raise RuntimeError("boom")

  monkeypatch.setitem(runner.STAGE_RUNNERS, "search_strategy", _ok("search_strategy"))
  monkeypatch.setitem(runner.STAGE_RUNNERS, "bigquery_light_retrieval", _ok("bigquery"))
  monkeypatch.setitem(runner.STAGE_RUNNERS, "technology_clustering_ranking", _fail)
  monkeypatch.setitem(runner.STAGE_RUNNERS, "top5_fulltext_collection", _ok("fulltext"))

  cfg.execute_bigquery = True
  result = runner.run_carbon_fiber_evidence_map_pipeline(cfg)
  assert result["run_id"]
  assert Path(result["manifest_path"]).exists()
  # After failure, later stages should be blocked (unless skipped).
  assert result["stage_statuses"]["technology_clustering_ranking"] == "failed"
  assert result["stage_statuses"]["top5_fulltext_collection"] == "blocked"

