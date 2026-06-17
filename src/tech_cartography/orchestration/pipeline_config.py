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

  fulltext_execute_limit: int | None = 1
  fulltext_publication_number: str | None = None
  fulltext_execute_top_n: int | None = None
  require_fulltext_execute_confirmation: bool = True
  confirm_fulltext_execute: bool = False

  fulltext_scope: str = "claims_only"
  maximum_fulltext_usd: float = 10.0
  allow_expensive_fulltext: bool = False
  fulltext_claims_first: bool = True

  maximum_bigquery_gb: float = 300.0
  maximum_fulltext_gb: float = 50.0
  max_results_total: int = 2000
  max_results_per_intent: int = 500
  top_n: int = 20
  fulltext_top_n: int = 5
  openalex_max_queries: int = 20
  openalex_max_results_per_query: int = 10
  execute_openalex_limited: bool = False
  openalex_use_claims_based_queries: bool = True

  skip_stages: list[str] = field(default_factory=list)
  start_stage: str | None = None
  stop_stage: str | None = None

  internal_cost_policy_name: str = "watch_run"
  internal_cost_policy_path: str = "configs/internal_cost_policy.yaml"
  enable_actual_cost_ledger: bool = True
  expose_cost_to_user: bool = False
  run_id: str | None = None

  manual_fulltext_input_dir: str = "outputs/manual_fulltext_inputs"
  enable_manual_fulltext_fallback: bool = True

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
      fulltext_execute_limit=data.get("fulltext_execute_limit", 1),
      fulltext_publication_number=data.get("fulltext_publication_number") or None,
      fulltext_execute_top_n=data.get("fulltext_execute_top_n") or None,
      require_fulltext_execute_confirmation=bool(
        data.get("require_fulltext_execute_confirmation", True),
      ),
      confirm_fulltext_execute=bool(data.get("confirm_fulltext_execute", False)),
      fulltext_scope=str(data.get("fulltext_scope", cls.fulltext_scope)),
      maximum_fulltext_usd=float(data.get("maximum_fulltext_usd", cls.maximum_fulltext_usd)),
      allow_expensive_fulltext=bool(data.get("allow_expensive_fulltext", False)),
      fulltext_claims_first=bool(data.get("fulltext_claims_first", True)),
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
      execute_openalex_limited=bool(data.get("execute_openalex_limited", False)),
      openalex_use_claims_based_queries=bool(data.get("openalex_use_claims_based_queries", True)),
      skip_stages=list(data.get("skip_stages", []) or []),
      start_stage=data.get("start_stage") or None,
      stop_stage=data.get("stop_stage") or None,
      internal_cost_policy_name=str(data.get("internal_cost_policy_name", cls.internal_cost_policy_name)),
      internal_cost_policy_path=str(data.get("internal_cost_policy_path", cls.internal_cost_policy_path)),
      enable_actual_cost_ledger=bool(data.get("enable_actual_cost_ledger", True)),
      expose_cost_to_user=bool(data.get("expose_cost_to_user", False)),
      run_id=data.get("run_id") or None,
      manual_fulltext_input_dir=str(
        data.get("manual_fulltext_input_dir", cls.manual_fulltext_input_dir),
      ),
      enable_manual_fulltext_fallback=bool(data.get("enable_manual_fulltext_fallback", True)),
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

