"""v8 Cloud Run Readiness schema (Phase 27N)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tech_cartography.runtime.v8_sources_schema import utc_now_iso

CLOUD_RUN_SAFETY_NOTICES: tuple[str, ...] = (
  "本 Phase では Cloud Build / Cloud Run deploy / gcloud 実行を行いません。",
  "Secret 値（API キー、SMTP パスワード、GCP credentials）は export / docs / UI に含めません。",
  "Cloud Run のファイルシステムは永続保存前提にしません — 一時出力は /tmp または LIVE_OUTPUTS_ROOT。",
  "メール送信と Scheduler は必須機能として保持しますが、Cloud Run 上ではデフォルト OFF です。",
  "Demo data not_ready は deploy 技術ブロッカーではありませんが、提出デモのブロッカーです。",
  "FTO、侵害、有効性判断、法的結論は行いません。",
)

CLOUD_RUN_NEXT_PHASES: tuple[str, ...] = (
  "Phase27O — Cloud Run v8反映",
  "Phase27P — 提出用README / スクショ / 動画準備",
)

CHECK_STATUS_VALUES: tuple[str, ...] = (
  "pass",
  "warning",
  "fail",
  "skipped",
)

OVERALL_STATUS_VALUES: tuple[str, ...] = (
  "ready_for_prepare",
  "ready_with_warnings",
  "blocked",
)


@dataclass
class V8CloudRunCheckResult:
  check_id: str
  check_name: str
  status: str
  summary: str = ""
  details: str = ""
  required_before_deploy: bool = True
  next_fix_hint: str = ""
  artifact_paths: list[str] = field(default_factory=list)
  no_secret_exposed: bool = True
  created_at: str = field(default_factory=utc_now_iso)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class V8CloudRunEnvVarSpec:
  name: str
  required: bool = False
  default_value_description: str = ""
  example_value: str = ""
  secret_value_allowed: bool = False
  should_use_secret_manager: bool = False
  purpose: str = ""
  used_in_files: list[str] = field(default_factory=list)
  warning: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class V8CloudRunArtifactPolicy:
  local_output_root: str = "outputs/local_*"
  cloud_output_root: str = "/tmp/tech_cartography_outputs"
  ephemeral_filesystem_notice: str = ""
  persistent_storage_required: bool = False
  recommended_storage_option: str = "local_tmp"
  affected_features: list[str] = field(default_factory=list)
  warning: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class V8CloudRunReadinessReport:
  report_id: str
  generated_at: str
  overall_status: str = "ready_with_warnings"
  app_entrypoint_status: str = "unknown"
  streamlit_command_status: str = "unknown"
  port_env_status: str = "unknown"
  requirements_status: str = "unknown"
  dockerfile_status: str = "unknown"
  output_artifact_policy_status: str = "unknown"
  secret_policy_status: str = "unknown"
  demo_data_status: str = "unknown"
  email_scheduler_status: str = "unknown"
  cloud_build_status: str = "not_executed"
  cloud_run_deploy_status: str = "not_executed"
  check_results: list[V8CloudRunCheckResult] = field(default_factory=list)
  env_var_specs: list[V8CloudRunEnvVarSpec] = field(default_factory=list)
  artifact_policy: V8CloudRunArtifactPolicy | None = None
  deploy_preparation_checklist: list[str] = field(default_factory=list)
  demo_data_checklist: list[str] = field(default_factory=list)
  operator_checklist: list[str] = field(default_factory=list)
  known_blockers: list[str] = field(default_factory=list)
  warnings: list[str] = field(default_factory=list)
  no_cloud_build_executed: bool = True
  no_cloud_run_deploy_executed: bool = True
  no_email_send: bool = True
  no_scheduler_start: bool = True
  no_secret_exposed: bool = True
  no_legal_judgement: bool = True

  def to_dict(self) -> dict[str, Any]:
    return {
      "report_id": self.report_id,
      "generated_at": self.generated_at,
      "overall_status": self.overall_status,
      "app_entrypoint_status": self.app_entrypoint_status,
      "streamlit_command_status": self.streamlit_command_status,
      "port_env_status": self.port_env_status,
      "requirements_status": self.requirements_status,
      "dockerfile_status": self.dockerfile_status,
      "output_artifact_policy_status": self.output_artifact_policy_status,
      "secret_policy_status": self.secret_policy_status,
      "demo_data_status": self.demo_data_status,
      "email_scheduler_status": self.email_scheduler_status,
      "cloud_build_status": self.cloud_build_status,
      "cloud_run_deploy_status": self.cloud_run_deploy_status,
      "check_results": [c.to_dict() for c in self.check_results],
      "env_var_specs": [e.to_dict() for e in self.env_var_specs],
      "artifact_policy": self.artifact_policy.to_dict() if self.artifact_policy else None,
      "deploy_preparation_checklist": self.deploy_preparation_checklist,
      "demo_data_checklist": self.demo_data_checklist,
      "operator_checklist": self.operator_checklist,
      "known_blockers": self.known_blockers,
      "warnings": self.warnings,
      "no_cloud_build_executed": self.no_cloud_build_executed,
      "no_cloud_run_deploy_executed": self.no_cloud_run_deploy_executed,
      "no_email_send": self.no_email_send,
      "no_scheduler_start": self.no_scheduler_start,
      "no_secret_exposed": self.no_secret_exposed,
      "no_legal_judgement": self.no_legal_judgement,
    }


@dataclass
class V8CloudRunReadinessExport:
  export_id: str
  output_dir: str
  json_path: str
  md_path: str
  manifest_path: str
  deploy_checklist_path: str
  demo_data_checklist_path: str
  operator_checklist_path: str
  env_var_template_path: str
  artifact_policy_path: str
  created_at: str

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)
