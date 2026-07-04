"""Tests for v9 cloud deploy assets."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_v9_uses_streamlit_service_command() -> None:
  text = (PROJECT_ROOT / "Dockerfile.v9").read_text(encoding="utf-8")
  assert "streamlit" in text
  assert "V9_ENABLE_CLOUD_SCHEDULER_ADMIN=false" in text
  assert "DISABLE_EMAIL_SEND=true" in text


def test_cloudbuild_v9_uses_dockerfile_v9_and_pushes_image() -> None:
  text = (PROJECT_ROOT / "cloudbuild.v9.yaml").read_text(encoding="utf-8")
  assert "Dockerfile.v9" in text
  assert "docker" in text
  assert "${_IMAGE_URI}" in text
  assert "push" in text


def test_v9_deploy_script_prepares_service_job_and_scheduler() -> None:
  text = (PROJECT_ROOT / "scripts" / "deploy_v9_cloud_run_weekly.sh").read_text(encoding="utf-8")
  required_tokens = [
    "scripts/run_v9_cloud_weekly_job.py",
    "cloudscheduler.googleapis.com",
    "gcloud run deploy",
    "gcloud run jobs create",
    "gcloud run jobs update",
    "gcloud scheduler jobs pause",
    "--region \"${REGION}\"",
    "--no-allow-unauthenticated",
    "--iap",
    "--tasks=1",
    "--parallelism=1",
    "--max-retries=0",
    "--task-timeout=30m",
    "--max-retry-attempts=0",
    "printf '%s\\n' '{\"enabled\": false}'",
    "gcloud run jobs execute",
    "V9_CLOUD_CHANGE_APPROVED=true",
    "MODE=\"${1:---plan}\"",
  ]
  assert all(token in text for token in required_tokens)


def test_dockerignore_excludes_local_secrets_and_artifacts() -> None:
  text = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
  required_lines = [
    ".env",
    ".env.*",
    "config/v9_weekly_run_config.local.json",
    "data/v9_runs",
  ]
  assert all(line in text for line in required_lines)


def test_build_command_uses_cloudbuild_yaml_and_not_invalid_file_flag() -> None:
  text = (PROJECT_ROOT / "scripts" / "deploy_v9_cloud_run_weekly.sh").read_text(encoding="utf-8")
  assert "--config cloudbuild.v9.yaml" in text
  assert "--substitutions \"_IMAGE_URI=${IMAGE_URI}\"" in text
  assert "--file Dockerfile.v9" not in text


def test_service_does_not_receive_smtp_or_tavily_secrets() -> None:
  text = (PROJECT_ROOT / "scripts" / "deploy_v9_cloud_run_weekly.sh").read_text(encoding="utf-8")
  service_section = text.split("service_deploy_cmd() {", 1)[1].split("job_deploy_cmd() {", 1)[0]
  assert "--set-secrets" not in service_section
  assert "SMTP_HOST=" not in service_section
  assert "SMTP_PORT=" not in service_section
  assert "SMTP_USERNAME=" not in service_section
  assert "SMTP_FROM_EMAIL=" not in service_section
  assert "TAVILY_API_KEY" not in service_section
  assert "SMTP_PASSWORD" not in service_section


def test_job_references_required_secrets_and_nonsecret_smtp_envs() -> None:
  text = (PROJECT_ROOT / "scripts" / "deploy_v9_cloud_run_weekly.sh").read_text(encoding="utf-8")
  job_section = text.split("job_deploy_cmd() {", 1)[1].split("bootstrap_settings_cmd() {", 1)[0]
  assert "SMTP_PASSWORD=${SMTP_PASSWORD_SECRET}:latest" in job_section
  assert "TAVILY_API_KEY=${TAVILY_API_KEY_SECRET}:latest" in job_section
  assert "SMTP_HOST=${SMTP_HOST}" in job_section
  assert "SMTP_PORT=${SMTP_PORT}" in job_section
  assert "SMTP_USERNAME=${SMTP_USERNAME}" in job_section
  assert "SMTP_FROM_EMAIL=${SMTP_FROM_EMAIL}" in job_section
  assert "V9_ENABLE_EMAIL_SEND=false" in job_section
  assert "DISABLE_EMAIL_SEND=true" in job_section
  assert "EMAIL_SEND_MODE=preview" in job_section


def test_scheduler_is_created_after_enabled_false_bootstrap_and_paused() -> None:
  text = (PROJECT_ROOT / "scripts" / "deploy_v9_cloud_run_weekly.sh").read_text(encoding="utf-8")
  bootstrap_index = text.index("bootstrap_settings_cmd()")
  scheduler_index = text.index("scheduler_create_cmd()")
  pause_index = text.index("scheduler_pause_cmd()")
  apply_body = text.split("apply_plan() {", 1)[1]
  assert bootstrap_index < scheduler_index < pause_index
  assert apply_body.index("bootstrap_settings_cmd") < apply_body.index("scheduler_create_cmd")
  assert apply_body.index("scheduler_create_cmd") < apply_body.index("scheduler_pause_cmd")


def test_apply_requires_approval_guard_and_plan_is_default() -> None:
  text = (PROJECT_ROOT / "scripts" / "deploy_v9_cloud_run_weekly.sh").read_text(encoding="utf-8")
  assert 'MODE="${1:---plan}"' in text
  assert 'if [[ "${V9_CLOUD_CHANGE_APPROVED:-false}" != "true" ]]' in text


def test_deploy_assets_do_not_target_existing_v7_or_v8_services() -> None:
  combined = "\n".join([
    (PROJECT_ROOT / "scripts" / "deploy_v9_cloud_run_weekly.sh").read_text(encoding="utf-8"),
    (PROJECT_ROOT / "cloudbuild.v9.yaml").read_text(encoding="utf-8"),
    (PROJECT_ROOT / "Dockerfile.v9").read_text(encoding="utf-8"),
  ])
  banned_tokens = [
    "tech-cartography-v7-demo",
    "tech-cartography-v7-live",
    "tech-cartography-v8-demo",
  ]
  assert all(token not in combined for token in banned_tokens)
