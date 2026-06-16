from __future__ import annotations

from pathlib import Path

from tech_cartography.orchestration.pipeline_config import PipelineConfig


def test_pipeline_config_from_yaml(tmp_path: Path) -> None:
  yaml_path = tmp_path / "cfg.yaml"
  yaml_path.write_text(
    "\n".join(
      [
        "theme: test",
        "run_name: demo",
        "execute_bigquery: false",
        "use_cache: true",
        "top_n: 20",
      ],
    ),
    encoding="utf-8",
  )
  cfg = PipelineConfig.from_yaml(str(yaml_path))
  assert cfg.theme == "test"
  assert cfg.run_name == "demo"
  assert cfg.execute_bigquery is False


def test_pipeline_config_defaults_safe() -> None:
  cfg = PipelineConfig()
  assert cfg.execute_bigquery is False
  assert cfg.execute_fulltext is False
  assert cfg.execute_openalex is False
  assert cfg.use_cache is True

