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
    "scripts/bootstrap_v9_cloud_weekly_settings.py",
    "cloudscheduler.googleapis.com",
    "iap.googleapis.com",
    "gcloud run deploy",
    "gcloud run jobs create",
    "gcloud run jobs update",
    "gcloud run jobs add-iam-policy-binding",
    "gcloud scheduler jobs pause",
    "--region \"${REGION}\"",
    "--no-allow-unauthenticated",
    "--iap",
    "--tasks=1",
    "--parallelism=1",
    "--max-retries=0",
    "--task-timeout=30m",
    "--max-retry-attempts=0",
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
  assert '--substitutions "_IMAGE_URI=${IMAGE_URI}"' in text
  assert "--file Dockerfile.v9" not in text


def test_service_does_not_receive_smtp_or_tavily_secrets() -> None:
  text = (PROJECT_ROOT / "scripts" / "deploy_v9_cloud_run_weekly.sh").read_text(encoding="utf-8")
  service_section = text.split("deploy_service() {", 1)[1].split("grant_iap_access() {", 1)[0]
  assert "--set-secrets" not in service_section
  assert "SMTP_HOST=" not in service_section
  assert "SMTP_PORT=" not in service_section
  assert "SMTP_USERNAME=" not in service_section
  assert "SMTP_FROM_EMAIL=" not in service_section
  assert "TAVILY_API_KEY" not in service_section
  assert "SMTP_PASSWORD" not in service_section


def test_job_references_required_secrets_and_nonsecret_smtp_envs() -> None:
  text = (PROJECT_ROOT / "scripts" / "deploy_v9_cloud_run_weekly.sh").read_text(encoding="utf-8")
  job_section = text.split("deploy_job() {", 1)[1].split("bootstrap_settings() {", 1)[0]
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
  bootstrap_index = text.index("bootstrap_settings() {")
  scheduler_index = text.index("deploy_scheduler() {")
  pause_index = text.index("pause_scheduler() {")
  apply_body = text.split("apply_plan() {", 1)[1]
  assert bootstrap_index < scheduler_index < pause_index
  assert apply_body.index("bootstrap_settings") < apply_body.index("deploy_scheduler")
  assert apply_body.index("deploy_scheduler") < apply_body.index("pause_scheduler")


def test_deploy_script_loads_nonsecret_smtp_values_without_echoing_secrets() -> None:
  text = (PROJECT_ROOT / "scripts" / "deploy_v9_cloud_run_weekly.sh").read_text(encoding="utf-8")
  assert "load_nonsecret_smtp_env_from_dotenv()" in text
  assert 'Path(".env")' in text
  assert "SMTP_USERNAME" in text and "SMTP_USER" in text
  assert "V9_ALLOWED_RECIPIENTS" in text
  assert "cat .env" not in text
  assert "set -x" not in text


def test_deploy_script_adds_required_bucket_secret_and_iap_steps() -> None:
  text = (PROJECT_ROOT / "scripts" / "deploy_v9_cloud_run_weekly.sh").read_text(encoding="utf-8")
  assert "gcloud storage buckets create" in text
  assert "roles/storage.objectUser" in text
  assert "roles/secretmanager.secretAccessor" in text
  assert "gcloud run services add-iam-policy-binding" in text
  assert "roles/run.invoker" in text
  assert "gcloud iap web add-iam-policy-binding" in text
  assert "roles/iap.httpsResourceAccessor" in text


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
