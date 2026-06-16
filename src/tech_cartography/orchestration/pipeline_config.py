"""Pipeline configuration for one-command case study runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import yaml


@dataclass
class PipelineConfig:
  theme: str = "PAN系炭素繊維"
  run_name: str | None = None
  output_root: str = "outputs/pipeline_runs"
  case_study_dir: str = "case_studies/carbon_fiber"
  profile_path: str = "configs/carbon_fiber_demo_profile.yaml"
  web_signal_file: str | None = None

  execute_bigquery: bool = False
  execute_fulltext: bool = False
  execute_openalex: bool = False
  use_cache: bool = True

  maximum_bigquery_gb: float = 300.0
  maximum_fulltext_gb: float = 50.0
  max_results_total: int = 2000
  max_results_per_intent: int = 500
  top_n: int = 20
  fulltext_top_n: int = 5
  openalex_max_queries: int = 20
  openalex_max_results_per_query: int = 10

  skip_stages: list[str] = field(default_factory=list)
  start_stage: str | None = None
  stop_stage: str | None = None

  # CLI-only convenience overrides (optional)
  use_existing_light_csv: str | None = None
  use_existing_top5_csv: str | None = None

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> PipelineConfig:
    return cls(
      theme=str(data.get("theme", cls.theme)),
      run_name=data.get("run_name"),
      output_root=str(data.get("output_root", cls.output_root)),
      case_study_dir=str(data.get("case_study_dir", cls.case_study_dir)),
      profile_path=str(data.get("profile_path", cls.profile_path)),
      web_signal_file=data.get("web_signal_file"),
      execute_bigquery=bool(data.get("execute_bigquery", False)),
      execute_fulltext=bool(data.get("execute_fulltext", False)),
      execute_openalex=bool(data.get("execute_openalex", False)),
      use_cache=bool(data.get("use_cache", True)),
      maximum_bigquery_gb=float(data.get("maximum_bigquery_gb", cls.maximum_bigquery_gb)),
      maximum_fulltext_gb=float(data.get("maximum_fulltext_gb", cls.maximum_fulltext_gb)),
      max_results_total=int(data.get("max_results_total", cls.max_results_total)),
      max_results_per_intent=int(data.get("max_results_per_intent", cls.max_results_per_intent)),
      top_n=int(data.get("top_n", cls.top_n)),
      fulltext_top_n=int(data.get("fulltext_top_n", cls.fulltext_top_n)),
      openalex_max_queries=int(data.get("openalex_max_queries", cls.openalex_max_queries)),
      openalex_max_results_per_query=int(
        data.get("openalex_max_results_per_query", cls.openalex_max_results_per_query),
      ),
      skip_stages=list(data.get("skip_stages", []) or []),
      start_stage=data.get("start_stage") or None,
      stop_stage=data.get("stop_stage") or None,
      use_existing_light_csv=data.get("use_existing_light_csv") or None,
      use_existing_top5_csv=data.get("use_existing_top5_csv") or None,
    )

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_yaml(cls, path: str) -> PipelineConfig:
    with open(path, encoding="utf-8") as handle:
      data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
      data = {}
    return cls.from_dict(data)

