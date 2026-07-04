#!/usr/bin/env bash
# Plan/apply deploy helper for Tech Cartography v9 Cloud Run weekly delivery.
set -euo pipefail

MODE="${1:---plan}"
PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-}"
JOB="${JOB:-}"
SCHEDULER_JOB="${SCHEDULER_JOB:-}"
BUCKET="${BUCKET:-}"
ARTIFACT_REPO="${ARTIFACT_REPO:-cloud-run-source-deploy}"
IMAGE_URI="${IMAGE_URI:-}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-}"
JOB_SERVICE_ACCOUNT="${JOB_SERVICE_ACCOUNT:-}"
SCHEDULER_SERVICE_ACCOUNT="${SCHEDULER_SERVICE_ACCOUNT:-}"
SMTP_PASSWORD_SECRET="${SMTP_PASSWORD_SECRET:-}"
TAVILY_API_KEY_SECRET="${TAVILY_API_KEY_SECRET:-}"
V9_WEEKLY_CONFIG_OBJECT="${V9_WEEKLY_CONFIG_OBJECT:-v9_config/weekly_delivery_config.json}"
V9_PERSIST_ROOT="${V9_PERSIST_ROOT:-/mnt/v9_persist}"
V9_ALLOWED_RECIPIENTS="${V9_ALLOWED_RECIPIENTS:-}"
SMTP_HOST="${SMTP_HOST:-}"
SMTP_PORT="${SMTP_PORT:-}"
SMTP_USERNAME="${SMTP_USERNAME:-}"
SMTP_FROM_EMAIL="${SMTP_FROM_EMAIL:-}"
SCHEDULER_TIME_ZONE="${SCHEDULER_TIME_ZONE:-Asia/Tokyo}"
SCHEDULER_SCHEDULE="${SCHEDULER_SCHEDULE:-0 9 * * 1}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if command -v conda >/dev/null 2>&1; then
  PY=(conda run -n "${CONDA_ENV:-2026hack}" python)
else
  PY=(python3)
fi

export PYTHONPATH="${ROOT}:${ROOT}/src"

log() {
  printf '%s\n' "$*"
}

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy_v9_cloud_run_weekly.sh --plan
  V9_CLOUD_CHANGE_APPROVED=true scripts/deploy_v9_cloud_run_weekly.sh --apply

Default mode is --plan. Cloud changes are never applied unless --apply is
specified and V9_CLOUD_CHANGE_APPROVED=true is present.
EOF
}

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    printf 'ERROR: %s is required for --apply.\n' "${name}" >&2
    exit 1
  fi
}

require_apply_guard() {
  if [[ "${V9_CLOUD_CHANGE_APPROVED:-false}" != "true" ]]; then
    log "ERROR: --apply requires V9_CLOUD_CHANGE_APPROVED=true"
    exit 1
  fi
}

run_local_checks() {
  "${PY[@]}" -m compileall services_v9 scripts ui_v9 tests app.py
  PYTHONPATH=.:src "${PY[@]}" -m pytest tests/test_v9_cloud_runtime_and_settings.py tests/test_v9_cloud_lock.py tests/test_v9_cloud_scheduler_admin.py tests/test_v9_cloud_weekly_job.py tests/test_v9_cloud_deploy_assets.py tests/test_v9_search_plan_ui.py -q
  PYTHONPATH=.:src "${PY[@]}" -m pytest tests/test_v9_*.py -q
  "${PY[@]}" scripts/check_v9_email_delivery_readiness.py
  "${PY[@]}" scripts/check_v9_scheduler_readiness.py
  "${PY[@]}" scripts/check_v9_cloud_weekly_readiness.py
}

resolve_image_uri() {
  if [[ -n "${IMAGE_URI}" ]]; then
    printf '%s\n' "${IMAGE_URI}"
    return 0
  fi
  printf '%s\n' "${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/${SERVICE}:latest"
}

enable_apis_cmd() {
  cat <<'EOF'
gcloud services enable \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  cloudbuild.googleapis.com \
  --project "${PROJECT_ID}"
EOF
}

build_cmd() {
  cat <<'EOF'
gcloud builds submit . \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --config cloudbuild.v9.yaml \
  --substitutions "_IMAGE_URI=${IMAGE_URI}"
EOF
}

service_deploy_cmd() {
  cat <<'EOF'
gcloud run deploy "${SERVICE}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --image "${IMAGE_URI}" \
  --no-allow-unauthenticated \
  --iap \
  --ingress all \
  --min-instances=0 \
  --max-instances=1 \
  --service-account "${SERVICE_ACCOUNT}" \
  --add-volume "name=v9-persist,type=cloud-storage,bucket=${BUCKET}" \
  --add-volume-mount "volume=v9-persist,mount-path=/mnt/v9_persist" \
  --set-env-vars "^@^GOOGLE_CLOUD_PROJECT=${PROJECT_ID}@V9_RUNTIME_MODE=cloud@V9_CLOUD_REGION=${REGION}@V9_STREAMLIT_SERVICE_NAME=${SERVICE}@V9_WEEKLY_JOB_NAME=${JOB}@V9_SCHEDULER_JOB_NAME=${SCHEDULER_JOB}@V9_SCHEDULER_REGION=${REGION}@V9_PERSIST_BUCKET=${BUCKET}@V9_PERSIST_ROOT=${V9_PERSIST_ROOT}@V9_WEEKLY_CONFIG_OBJECT=${V9_WEEKLY_CONFIG_OBJECT}@V9_ALLOWED_RECIPIENTS=${V9_ALLOWED_RECIPIENTS}@V9_ENABLE_CLOUD_SCHEDULER_ADMIN=false@DISABLE_EMAIL_SEND=true@EMAIL_SEND_MODE=preview"
EOF
}

job_deploy_cmd() {
  cat <<'EOF'
if gcloud run jobs describe "${JOB}" --project "${PROJECT_ID}" --region "${REGION}" >/dev/null 2>&1; then
  gcloud run jobs update "${JOB}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --image "${IMAGE_URI}" \
    --command python \
    --args scripts/run_v9_cloud_weekly_job.py \
    --tasks=1 \
    --parallelism=1 \
    --max-retries=0 \
    --task-timeout=30m \
    --service-account "${JOB_SERVICE_ACCOUNT}" \
    --add-volume "name=v9-persist,type=cloud-storage,bucket=${BUCKET}" \
    --add-volume-mount "volume=v9-persist,mount-path=/mnt/v9_persist" \
    --set-env-vars "^@^GOOGLE_CLOUD_PROJECT=${PROJECT_ID}@V9_RUNTIME_MODE=cloud@V9_CLOUD_REGION=${REGION}@V9_WEEKLY_JOB_NAME=${JOB}@V9_PERSIST_BUCKET=${BUCKET}@V9_PERSIST_ROOT=${V9_PERSIST_ROOT}@V9_WEEKLY_CONFIG_OBJECT=${V9_WEEKLY_CONFIG_OBJECT}@V9_ALLOWED_RECIPIENTS=${V9_ALLOWED_RECIPIENTS}@SMTP_HOST=${SMTP_HOST}@SMTP_PORT=${SMTP_PORT}@SMTP_USERNAME=${SMTP_USERNAME}@SMTP_FROM_EMAIL=${SMTP_FROM_EMAIL}@V9_ENABLE_EMAIL_SEND=false@DISABLE_EMAIL_SEND=true@EMAIL_SEND_MODE=preview" \
    --set-secrets "SMTP_PASSWORD=${SMTP_PASSWORD_SECRET}:latest,TAVILY_API_KEY=${TAVILY_API_KEY_SECRET}:latest"
else
  gcloud run jobs create "${JOB}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --image "${IMAGE_URI}" \
    --command python \
    --args scripts/run_v9_cloud_weekly_job.py \
    --tasks=1 \
    --parallelism=1 \
    --max-retries=0 \
    --task-timeout=30m \
    --service-account "${JOB_SERVICE_ACCOUNT}" \
    --add-volume "name=v9-persist,type=cloud-storage,bucket=${BUCKET}" \
    --add-volume-mount "volume=v9-persist,mount-path=/mnt/v9_persist" \
    --set-env-vars "^@^GOOGLE_CLOUD_PROJECT=${PROJECT_ID}@V9_RUNTIME_MODE=cloud@V9_CLOUD_REGION=${REGION}@V9_WEEKLY_JOB_NAME=${JOB}@V9_PERSIST_BUCKET=${BUCKET}@V9_PERSIST_ROOT=${V9_PERSIST_ROOT}@V9_WEEKLY_CONFIG_OBJECT=${V9_WEEKLY_CONFIG_OBJECT}@V9_ALLOWED_RECIPIENTS=${V9_ALLOWED_RECIPIENTS}@SMTP_HOST=${SMTP_HOST}@SMTP_PORT=${SMTP_PORT}@SMTP_USERNAME=${SMTP_USERNAME}@SMTP_FROM_EMAIL=${SMTP_FROM_EMAIL}@V9_ENABLE_EMAIL_SEND=false@DISABLE_EMAIL_SEND=true@EMAIL_SEND_MODE=preview" \
    --set-secrets "SMTP_PASSWORD=${SMTP_PASSWORD_SECRET}:latest,TAVILY_API_KEY=${TAVILY_API_KEY_SECRET}:latest"
fi
EOF
}

bootstrap_settings_cmd() {
  cat <<'EOF'
printf '%s\n' '{"enabled": false}' | \
  gcloud storage cp - "gs://${BUCKET}/${V9_WEEKLY_CONFIG_OBJECT}" --project "${PROJECT_ID}"
EOF
}

manual_skip_test_cmd() {
  cat <<'EOF'
gcloud run jobs execute "${JOB}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --wait
EOF
}

scheduler_create_cmd() {
  cat <<'EOF'
if gcloud scheduler jobs describe "${SCHEDULER_JOB}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "${SCHEDULER_JOB}" \
    --project "${PROJECT_ID}" \
    --location "${REGION}" \
    --schedule "${SCHEDULER_SCHEDULE}" \
    --time-zone "${SCHEDULER_TIME_ZONE}" \
    --uri "https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs/${JOB}:run" \
    --http-method POST \
    --oauth-service-account-email "${SCHEDULER_SERVICE_ACCOUNT}" \
    --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform" \
    --max-retry-attempts=0
else
  gcloud scheduler jobs create http "${SCHEDULER_JOB}" \
    --project "${PROJECT_ID}" \
    --location "${REGION}" \
    --schedule "${SCHEDULER_SCHEDULE}" \
    --time-zone "${SCHEDULER_TIME_ZONE}" \
    --uri "https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs/${JOB}:run" \
    --http-method POST \
    --oauth-service-account-email "${SCHEDULER_SERVICE_ACCOUNT}" \
    --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform" \
    --max-retry-attempts=0
fi
EOF
}

scheduler_pause_cmd() {
  cat <<'EOF'
gcloud scheduler jobs pause "${SCHEDULER_JOB}" \
  --project "${PROJECT_ID}" \
  --location "${REGION}"
EOF
}

scheduler_verify_pause_cmd() {
  cat <<'EOF'
gcloud scheduler jobs describe "${SCHEDULER_JOB}" \
  --project "${PROJECT_ID}" \
  --location "${REGION}" \
  --format="value(state)"
EOF
}

print_plan() {
  cat <<'EOF'
Cloud deploy plan only. No commands have been executed.

## Enable APIs
EOF
  enable_apis_cmd
  cat <<'EOF'

## Build image
EOF
  build_cmd
  cat <<'EOF'

## Deploy authenticated Streamlit Service
EOF
  service_deploy_cmd
  cat <<'EOF'

## Deploy Cloud Run Job
EOF
  job_deploy_cmd
  cat <<'EOF'

## Bootstrap enabled=false settings object
EOF
  bootstrap_settings_cmd
  cat <<'EOF'

## Manual skip test before Scheduler
EOF
  manual_skip_test_cmd
  cat <<'EOF'

## Create or update Scheduler
EOF
  scheduler_create_cmd
  cat <<'EOF'

## Pause Scheduler immediately
EOF
  scheduler_pause_cmd
  cat <<'EOF'

## Verify pause state
EOF
  scheduler_verify_pause_cmd
}

apply_plan() {
  require_apply_guard
  require_var PROJECT_ID
  require_var SERVICE
  require_var JOB
  require_var SCHEDULER_JOB
  require_var BUCKET
  require_var SERVICE_ACCOUNT
  require_var JOB_SERVICE_ACCOUNT
  require_var SCHEDULER_SERVICE_ACCOUNT
  require_var SMTP_PASSWORD_SECRET
  require_var TAVILY_API_KEY_SECRET
  require_var V9_ALLOWED_RECIPIENTS
  require_var SMTP_HOST
  require_var SMTP_PORT
  require_var SMTP_USERNAME
  require_var SMTP_FROM_EMAIL
  IMAGE_URI="$(resolve_image_uri)"

  run_local_checks
  eval "$(enable_apis_cmd)"
  eval "$(build_cmd)"
  eval "$(service_deploy_cmd)"
  eval "$(job_deploy_cmd)"
  eval "$(bootstrap_settings_cmd)"
  eval "$(manual_skip_test_cmd)"
  eval "$(scheduler_create_cmd)"
  eval "$(scheduler_pause_cmd)"
  eval "$(scheduler_verify_pause_cmd)"
}

main() {
  case "${MODE}" in
    --plan)
      IMAGE_URI='${IMAGE_URI}'
      print_plan
      ;;
    --apply)
      apply_plan
      ;;
    -h|--help)
      usage
      ;;
    *)
      log "ERROR: unsupported mode: ${MODE}"
      usage
      exit 1
      ;;
  esac
}

main
