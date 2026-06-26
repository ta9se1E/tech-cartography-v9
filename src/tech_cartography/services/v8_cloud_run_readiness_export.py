"""v8 Cloud Run Readiness export (Phase 27N)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from tech_cartography.runtime.live_artifact_paths import LIVE_OUTPUTS_ROOT_ENV
from tech_cartography.runtime.live_artifact_paths import get_live_outputs_root
from tech_cartography.runtime.v8_cloud_run_readiness_schema import (
  CLOUD_RUN_NEXT_PHASES,
  CLOUD_RUN_SAFETY_NOTICES,
  V8CloudRunReadinessExport,
  V8CloudRunReadinessReport,
)

V8_CLOUD_RUN_READINESS_SUBDIR = "v8_cloud_run_readiness"
LOCAL_V8_CLOUD_RUN_READINESS_SUBDIR = "local_v8_cloud_run_readiness"

_SENSITIVE_RE = re.compile(
  r"(smtp_password\s*[:=]\s*\S+|tavily_api_key\s*[:=]\s*\S+|api[_-]?key\s*[:=]\s*\S{8,}|"
  r"authorization:\s*bearer\s+\S+|oauth|eyJhbGci)",
  re.IGNORECASE,
)


def get_cloud_run_readiness_dir(project_root: Path | str | None = None) -> Path:
  root = get_live_outputs_root(project_root)
  if root.name == "outputs" or not str(root).endswith("live"):
    return root / LOCAL_V8_CLOUD_RUN_READINESS_SUBDIR
  return root / V8_CLOUD_RUN_READINESS_SUBDIR


def find_latest_cloud_run_readiness_dir(project_root: Path | str | None = None) -> Path | None:
  base = get_cloud_run_readiness_dir(project_root)
  if not base.is_dir():
    return None
  dirs = sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
  return dirs[0] if dirs else None


def _assert_no_secrets(text: str) -> None:
  if _SENSITIVE_RE.search(text):
    raise ValueError("export content must not contain secret-like strings")


def deploy_preparation_checklist_md(report: V8CloudRunReadinessReport) -> str:
  lines = [
    "# Deploy Preparation Checklist (Phase27N — prepare only)",
    "",
    f"- overall_status: {report.overall_status}",
    f"- no_cloud_build_executed: {report.no_cloud_build_executed}",
    f"- no_cloud_run_deploy_executed: {report.no_cloud_run_deploy_executed}",
    "",
    "## Checklist",
    *[f"- [ ] {item}" for item in report.deploy_preparation_checklist],
    "",
    "## Known Blockers",
  ]
  if report.known_blockers:
    lines.extend(f"- {b}" for b in report.known_blockers)
  else:
    lines.append("- (none — deploy 技術ブロッカーなし)")
  lines.extend(["", "## Next Phases", *[f"- {p}" for p in CLOUD_RUN_NEXT_PHASES]])
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def demo_data_checklist_md(report: V8CloudRunReadinessReport) -> str:
  lines = [
    "# Demo Data Checklist",
    "",
    f"- demo_data_status: {report.demo_data_status}",
    "",
    "Demo Readiness not_ready は **Cloud Run deploy の技術ブロッカーではありません**。"
    " ただし **提出デモのブロッカー** として扱います。",
    "",
    "## Checklist",
    *[f"- [ ] {item}" for item in report.demo_data_checklist],
    "",
    "## Warnings",
  ]
  if report.warnings:
    lines.extend(f"- {w}" for w in report.warnings)
  else:
    lines.append("- (none)")
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def operator_checklist_md(report: V8CloudRunReadinessReport) -> str:
  lines = [
    "# Cloud Run Operator Checklist",
    "",
    "## Checklist",
    *[f"- [ ] {item}" for item in report.operator_checklist],
    "",
    "## Safety",
    *[f"- {n}" for n in CLOUD_RUN_SAFETY_NOTICES],
  ]
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def env_var_template_md(report: V8CloudRunReadinessReport) -> str:
  lines = [
    "# Environment Variable Template (no secret values)",
    "",
    "Secret 値は **このファイルに書かない** — Secret Manager から注入。",
    "",
    "| Name | Required | Default / Example | Purpose |",
    "|------|----------|-------------------|---------|",
  ]
  for spec in report.env_var_specs:
    example = spec.example_value or spec.default_value_description
    lines.append(
      f"| {spec.name} | {spec.required} | {example} | {spec.purpose} |"
    )
    if spec.should_use_secret_manager:
      lines.append(f"| | | Secret Manager 推奨 | {spec.warning or '値を docs に書かない'} |")
  lines.extend([
    "",
    "## Cloud Run 推奨（Phase27O 参考 — この Phase では実行しない）",
    "",
    "```bash",
    "# 実行しない — Phase27O まで保留",
    "# gcloud run deploy ... \\",
    "#   --set-env-vars APP_UI_VERSION=v8,DISABLE_EMAIL_SEND=true,DISABLE_SCHEDULER=true,\\",
    f"#   {LIVE_OUTPUTS_ROOT_ENV}=/tmp/tech_cartography_outputs",
    "```",
  ])
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def artifact_policy_md(report: V8CloudRunReadinessReport) -> str:
  policy = report.artifact_policy
  lines = [
    "# Output Artifact Policy",
    "",
  ]
  if policy:
    lines.extend([
      f"- local_output_root: {policy.local_output_root}",
      f"- cloud_output_root: {policy.cloud_output_root}",
      f"- recommended_storage_option: {policy.recommended_storage_option}",
      f"- persistent_storage_required: {policy.persistent_storage_required}",
      "",
      "## Ephemeral Filesystem",
      policy.ephemeral_filesystem_notice,
      "",
      "## Affected Features",
      *[f"- {f}" for f in policy.affected_features],
      "",
      f"**Warning:** {policy.warning}",
    ])
  lines.extend(["", "## Safety", *[f"- {n}" for n in CLOUD_RUN_SAFETY_NOTICES]])
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def report_to_markdown(report: V8CloudRunReadinessReport) -> str:
  lines = [
    "# Cloud Run Readiness Report (Phase27N)",
    "",
    f"- report_id: {report.report_id}",
    f"- generated_at: {report.generated_at}",
    f"- overall_status: {report.overall_status}",
    "",
    "## Status Summary",
    f"- app_entrypoint: {report.app_entrypoint_status}",
    f"- streamlit_command: {report.streamlit_command_status}",
    f"- port_env: {report.port_env_status}",
    f"- requirements: {report.requirements_status}",
    f"- dockerfile: {report.dockerfile_status}",
    f"- output_artifact_policy: {report.output_artifact_policy_status}",
    f"- secret_policy: {report.secret_policy_status}",
    f"- demo_data: {report.demo_data_status}",
    f"- email_scheduler: {report.email_scheduler_status}",
    f"- cloud_build: {report.cloud_build_status}",
    f"- cloud_run_deploy: {report.cloud_run_deploy_status}",
    "",
    "## Check Results",
  ]
  for check in report.check_results:
    lines.append(f"- **{check.check_name}** [{check.status}]: {check.summary}")
    if check.next_fix_hint:
      lines.append(f"  - fix: {check.next_fix_hint}")

  lines.extend([
    "",
    "## Known Blockers",
  ])
  if report.known_blockers:
    lines.extend(f"- {b}" for b in report.known_blockers)
  else:
    lines.append("- (none)")

  lines.extend([
    "",
    "## Warnings",
  ])
  if report.warnings:
    lines.extend(f"- {w}" for w in report.warnings)
  else:
    lines.append("- (none)")

  lines.extend([
    "",
    "## Notices",
    f"- no_cloud_build_executed: {report.no_cloud_build_executed}",
    f"- no_cloud_run_deploy_executed: {report.no_cloud_run_deploy_executed}",
    f"- no_email_send: {report.no_email_send}",
    f"- no_scheduler_start: {report.no_scheduler_start}",
    "",
    "## Safety",
    *[f"- {n}" for n in CLOUD_RUN_SAFETY_NOTICES],
  ])
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def export_cloud_run_readiness(
  report: V8CloudRunReadinessReport,
  *,
  project_root: Path | str | None = None,
) -> V8CloudRunReadinessExport:
  root = Path(project_root).resolve() if project_root else Path.cwd().resolve()
  slug = report.generated_at.replace(":", "").replace("-", "").replace("+00:00", "Z")
  output_dir = get_cloud_run_readiness_dir(root) / f"readiness_{slug}"
  output_dir.mkdir(parents=True, exist_ok=True)

  json_path = output_dir / "cloud_run_readiness_report.json"
  md_path = output_dir / "cloud_run_readiness_report.md"
  manifest_path = output_dir / "cloud_run_readiness_manifest.json"
  deploy_path = output_dir / "deploy_preparation_checklist.md"
  demo_path = output_dir / "demo_data_checklist.md"
  operator_path = output_dir / "operator_checklist.md"
  env_path = output_dir / "env_var_template.md"
  policy_path = output_dir / "artifact_policy.md"

  json_text = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
  _assert_no_secrets(json_text)
  json_path.write_text(json_text, encoding="utf-8")

  md_text = report_to_markdown(report)
  md_path.write_text(md_text, encoding="utf-8")

  deploy_path.write_text(deploy_preparation_checklist_md(report), encoding="utf-8")
  demo_path.write_text(demo_data_checklist_md(report), encoding="utf-8")
  operator_path.write_text(operator_checklist_md(report), encoding="utf-8")
  env_path.write_text(env_var_template_md(report), encoding="utf-8")
  policy_path.write_text(artifact_policy_md(report), encoding="utf-8")

  manifest = {
    "export_id": report.report_id,
    "generated_at": report.generated_at,
    "overall_status": report.overall_status,
    "output_dir": str(output_dir),
    "files": [
      json_path.name,
      md_path.name,
      manifest_path.name,
      deploy_path.name,
      demo_path.name,
      operator_path.name,
      env_path.name,
      policy_path.name,
    ],
    "no_cloud_build_executed": report.no_cloud_build_executed,
    "no_cloud_run_deploy_executed": report.no_cloud_run_deploy_executed,
  }
  manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2)
  manifest_path.write_text(manifest_text, encoding="utf-8")

  from tech_cartography.runtime.v8_sources_schema import utc_now_iso

  return V8CloudRunReadinessExport(
    export_id=report.report_id,
    output_dir=str(output_dir),
    json_path=str(json_path),
    md_path=str(md_path),
    manifest_path=str(manifest_path),
    deploy_checklist_path=str(deploy_path),
    demo_data_checklist_path=str(demo_path),
    operator_checklist_path=str(operator_path),
    env_var_template_path=str(env_path),
    artifact_policy_path=str(policy_path),
    created_at=utc_now_iso(),
  )
