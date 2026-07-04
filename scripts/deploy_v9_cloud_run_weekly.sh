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

get_project_number() {
  gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)"
}

get_active_account() {
  gcloud auth list --filter=status:ACTIVE --format="value(account)"
}

load_nonsecret_smtp_env_from_dotenv() {
  local export_lines
  export_lines="$("${PY[@]}" -c '
from pathlib import Path
import shlex
path = Path(".env")
values = {}
if path.exists():
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"")
        values[key] = value
resolved = {
    "SMTP_HOST": values.get("SMTP_HOST", ""),
    "SMTP_PORT": values.get("SMTP_PORT", ""),
    "SMTP_USERNAME": values.get("SMTP_USERNAME") or values.get("SMTP_USER", ""),
    "SMTP_FROM_EMAIL": values.get("SMTP_FROM_EMAIL", ""),
}
resolved["V9_ALLOWED_RECIPIENTS"] = resolved["SMTP_FROM_EMAIL"]
for key, value in resolved.items():
    if value:
        print(f"export {key}={shlex.quote(value)}")
')"
  if [[ -n "${export_lines}" ]]; then
    eval "${export_lines}"
  fi
}

enable_required_apis() {
  gcloud services enable \
    run.googleapis.com \
    cloudscheduler.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    storage.googleapis.com \
    cloudbuild.googleapis.com \
    iap.googleapis.com \
    --project "${PROJECT_ID}"
}

ensure_service_account() {
  local email="$1"
  local account_id="$2"
  local display_name="$3"
  if gcloud iam service-accounts describe "${email}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    log "Service account exists: ${email}"
    return 0
  fi
  gcloud iam service-accounts create "${account_id}" \
    --project "${PROJECT_ID}" \
    --display-name "${display_name}"
}

ensure_bucket() {
  if gcloud storage buckets describe "gs://${BUCKET}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    log "Bucket exists: gs://${BUCKET}"
    return 0
  fi
  gcloud storage buckets create "gs://${BUCKET}" \
    --project "${PROJECT_ID}" \
    --location "${REGION}" \
    --default-storage-class STANDARD \
    --uniform-bucket-level-access
}

grant_bucket_iam() {
  local member_email="$1"
  gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
    --project "${PROJECT_ID}" \
    --member "serviceAccount:${member_email}" \
    --role "roles/storage.objectUser"
}

grant_secret_iam() {
  local secret_name="$1"
  local member_email="$2"
  gcloud secrets add-iam-policy-binding "${secret_name}" \
    --project "${PROJECT_ID}" \
    --member "serviceAccount:${member_email}" \
    --role "roles/secretmanager.secretAccessor"
}

build_image() {
  IMAGE_URI="$(resolve_image_uri)"
  gcloud builds submit . \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --config cloudbuild.v9.yaml \
    --substitutions "_IMAGE_URI=${IMAGE_URI}"
}

deploy_service() {
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
    --set-env-vars "^#^GOOGLE_CLOUD_PROJECT=${PROJECT_ID}#V9_RUNTIME_MODE=cloud#V9_CLOUD_REGION=${REGION}#V9_STREAMLIT_SERVICE_NAME=${SERVICE}#V9_WEEKLY_JOB_NAME=${JOB}#V9_SCHEDULER_JOB_NAME=${SCHEDULER_JOB}#V9_SCHEDULER_REGION=${REGION}#V9_PERSIST_BUCKET=${BUCKET}#V9_PERSIST_ROOT=${V9_PERSIST_ROOT}#V9_WEEKLY_CONFIG_OBJECT=${V9_WEEKLY_CONFIG_OBJECT}#V9_ALLOWED_RECIPIENTS=${V9_ALLOWED_RECIPIENTS}#V9_ENABLE_CLOUD_SCHEDULER_ADMIN=false#DISABLE_EMAIL_SEND=true#EMAIL_SEND_MODE=preview"
}

grant_iap_access() {
  local project_number active_account iap_service_agent
  project_number="$(get_project_number)"
  active_account="$(get_active_account)"
  iap_service_agent="service-${project_number}@gcp-sa-iap.iam.gserviceaccount.com"
  gcloud beta services identity create --service=iap.googleapis.com --project="${PROJECT_ID}" >/dev/null 2>&1 || true
  gcloud run services add-iam-policy-binding "${SERVICE}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --member "serviceAccount:${iap_service_agent}" \
    --role "roles/run.invoker"
  gcloud iap web add-iam-policy-binding \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --resource-type=cloud-run \
    --service "${SERVICE}" \
    --member "user:${active_account}" \
    --role "roles/iap.httpsResourceAccessor"
}

deploy_job() {
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
      --set-env-vars "^#^GOOGLE_CLOUD_PROJECT=${PROJECT_ID}#V9_RUNTIME_MODE=cloud#V9_CLOUD_REGION=${REGION}#V9_WEEKLY_JOB_NAME=${JOB}#V9_PERSIST_BUCKET=${BUCKET}#V9_PERSIST_ROOT=${V9_PERSIST_ROOT}#V9_WEEKLY_CONFIG_OBJECT=${V9_WEEKLY_CONFIG_OBJECT}#V9_ALLOWED_RECIPIENTS=${V9_ALLOWED_RECIPIENTS}#SMTP_HOST=${SMTP_HOST}#SMTP_PORT=${SMTP_PORT}#SMTP_USERNAME=${SMTP_USERNAME}#SMTP_FROM_EMAIL=${SMTP_FROM_EMAIL}#V9_ENABLE_EMAIL_SEND=false#DISABLE_EMAIL_SEND=true#EMAIL_SEND_MODE=preview" \
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
      --set-env-vars "^#^GOOGLE_CLOUD_PROJECT=${PROJECT_ID}#V9_RUNTIME_MODE=cloud#V9_CLOUD_REGION=${REGION}#V9_WEEKLY_JOB_NAME=${JOB}#V9_PERSIST_BUCKET=${BUCKET}#V9_PERSIST_ROOT=${V9_PERSIST_ROOT}#V9_WEEKLY_CONFIG_OBJECT=${V9_WEEKLY_CONFIG_OBJECT}#V9_ALLOWED_RECIPIENTS=${V9_ALLOWED_RECIPIENTS}#SMTP_HOST=${SMTP_HOST}#SMTP_PORT=${SMTP_PORT}#SMTP_USERNAME=${SMTP_USERNAME}#SMTP_FROM_EMAIL=${SMTP_FROM_EMAIL}#V9_ENABLE_EMAIL_SEND=false#DISABLE_EMAIL_SEND=true#EMAIL_SEND_MODE=preview" \
      --set-secrets "SMTP_PASSWORD=${SMTP_PASSWORD_SECRET}:latest,TAVILY_API_KEY=${TAVILY_API_KEY_SECRET}:latest"
  fi
}

bootstrap_settings() {
  "${PY[@]}" scripts/bootstrap_v9_cloud_weekly_settings.py
}

manual_skip_test() {
  gcloud run jobs execute "${JOB}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --wait
}

grant_scheduler_invoker() {
  gcloud run jobs add-iam-policy-binding "${JOB}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --member "serviceAccount:${SCHEDULER_SERVICE_ACCOUNT}" \
    --role "roles/run.invoker"
}

deploy_scheduler() {
  local run_uri="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs/${JOB}:run"
  if gcloud scheduler jobs describe "${SCHEDULER_JOB}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud scheduler jobs update http "${SCHEDULER_JOB}" \
      --project "${PROJECT_ID}" \
      --location "${REGION}" \
      --schedule "${SCHEDULER_SCHEDULE}" \
      --time-zone "${SCHEDULER_TIME_ZONE}" \
      --uri "${run_uri}" \
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
      --uri "${run_uri}" \
      --http-method POST \
      --oauth-service-account-email "${SCHEDULER_SERVICE_ACCOUNT}" \
      --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform" \
      --max-retry-attempts=0
  fi
}

pause_scheduler() {
  gcloud scheduler jobs pause "${SCHEDULER_JOB}" \
    --project "${PROJECT_ID}" \
    --location "${REGION}"
}

verify_scheduler_pause() {
  gcloud scheduler jobs describe "${SCHEDULER_JOB}" \
    --project "${PROJECT_ID}" \
    --location "${REGION}" \
    --format="value(state)"
}

print_plan() {
  local project_number image_preview
  image_preview="$(resolve_image_uri)"
  project_number='${PROJECT_NUMBER}'
  cat <<EOF
Cloud deploy plan only. No commands have been executed.

Resolved resource targets:
- project: ${PROJECT_ID}
- region: ${REGION}
- service: ${SERVICE}
- job: ${JOB}
- scheduler: ${SCHEDULER_JOB}
- bucket: ${BUCKET}
- artifact repository: ${ARTIFACT_REPO}
- image: ${image_preview}
- service SA: ${SERVICE_ACCOUNT}
- job SA: ${JOB_SERVICE_ACCOUNT}
- scheduler SA: ${SCHEDULER_SERVICE_ACCOUNT}
- SMTP secret: ${SMTP_PASSWORD_SECRET}
- Tavily secret: ${TAVILY_API_KEY_SECRET}
- bootstrap settings object: gs://${BUCKET}/${V9_WEEKLY_CONFIG_OBJECT}

Planned order:
1. enable required APIs
2. ensure service accounts
3. ensure bucket
4. bucket IAM
5. secret IAM
6. Cloud Build image build/push
7. deploy Cloud Run Service
8. apply IAP access bindings
9. deploy Cloud Run Job
10. bootstrap enabled=false settings via existing cloud_weekly_settings
11. execute Job once and confirm skip
12. grant Scheduler invoker on Job
13. create or update Scheduler
14. pause Scheduler and verify PAUSED

## Enable APIs
gcloud services enable \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  cloudbuild.googleapis.com \
  iap.googleapis.com \
  --project "${PROJECT_ID}"

## Ensure service accounts
gcloud iam service-accounts describe "${SERVICE_ACCOUNT}" --project "${PROJECT_ID}" || \
  gcloud iam service-accounts create "${SERVICE_ACCOUNT%%@*}" --project "${PROJECT_ID}" --display-name "Tech Cartography v9 Streamlit Service"
gcloud iam service-accounts describe "${JOB_SERVICE_ACCOUNT}" --project "${PROJECT_ID}" || \
  gcloud iam service-accounts create "${JOB_SERVICE_ACCOUNT%%@*}" --project "${PROJECT_ID}" --display-name "Tech Cartography v9 Weekly Job"
gcloud iam service-accounts describe "${SCHEDULER_SERVICE_ACCOUNT}" --project "${PROJECT_ID}" || \
  gcloud iam service-accounts create "${SCHEDULER_SERVICE_ACCOUNT%%@*}" --project "${PROJECT_ID}" --display-name "Tech Cartography v9 Scheduler Invoker"

## Ensure bucket
gcloud storage buckets describe "gs://${BUCKET}" --project "${PROJECT_ID}" || \
  gcloud storage buckets create "gs://${BUCKET}" --project "${PROJECT_ID}" --location "${REGION}" --default-storage-class STANDARD --uniform-bucket-level-access

## Bucket IAM
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" --project "${PROJECT_ID}" --member "serviceAccount:${SERVICE_ACCOUNT}" --role "roles/storage.objectUser"
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" --project "${PROJECT_ID}" --member "serviceAccount:${JOB_SERVICE_ACCOUNT}" --role "roles/storage.objectUser"

## Secret IAM
gcloud secrets add-iam-policy-binding "${SMTP_PASSWORD_SECRET}" --project "${PROJECT_ID}" --member "serviceAccount:${JOB_SERVICE_ACCOUNT}" --role "roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding "${TAVILY_API_KEY_SECRET}" --project "${PROJECT_ID}" --member "serviceAccount:${JOB_SERVICE_ACCOUNT}" --role "roles/secretmanager.secretAccessor"

## Build image
gcloud builds submit . \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --config cloudbuild.v9.yaml \
  --substitutions "_IMAGE_URI=${image_preview}"

## Deploy authenticated Streamlit Service
gcloud run deploy "${SERVICE}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --image "${image_preview}" \
  --no-allow-unauthenticated \
  --iap \
  --ingress all \
  --min-instances=0 \
  --max-instances=1 \
  --service-account "${SERVICE_ACCOUNT}" \
  --add-volume "name=v9-persist,type=cloud-storage,bucket=${BUCKET}" \
  --add-volume-mount "volume=v9-persist,mount-path=/mnt/v9_persist" \
  --set-env-vars "^#^GOOGLE_CLOUD_PROJECT=${PROJECT_ID}#V9_RUNTIME_MODE=cloud#V9_CLOUD_REGION=${REGION}#V9_STREAMLIT_SERVICE_NAME=${SERVICE}#V9_WEEKLY_JOB_NAME=${JOB}#V9_SCHEDULER_JOB_NAME=${SCHEDULER_JOB}#V9_SCHEDULER_REGION=${REGION}#V9_PERSIST_BUCKET=${BUCKET}#V9_PERSIST_ROOT=${V9_PERSIST_ROOT}#V9_WEEKLY_CONFIG_OBJECT=${V9_WEEKLY_CONFIG_OBJECT}#V9_ALLOWED_RECIPIENTS=\${V9_ALLOWED_RECIPIENTS}#V9_ENABLE_CLOUD_SCHEDULER_ADMIN=false#DISABLE_EMAIL_SEND=true#EMAIL_SEND_MODE=preview"

## IAP access bindings
gcloud run services add-iam-policy-binding "${SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --member "serviceAccount:service-\${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com" --role "roles/run.invoker"
gcloud iap web add-iam-policy-binding --project "${PROJECT_ID}" --region "${REGION}" --resource-type=cloud-run --service "${SERVICE}" --member "user:\${ACTIVE_ACCOUNT}" --role "roles/iap.httpsResourceAccessor"

## Deploy Cloud Run Job
if gcloud run jobs describe "${JOB}" --project "${PROJECT_ID}" --region "${REGION}" >/dev/null 2>&1; then
  gcloud run jobs update "${JOB}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --image "${image_preview}" \
    --command python \
    --args scripts/run_v9_cloud_weekly_job.py \
    --tasks=1 \
    --parallelism=1 \
    --max-retries=0 \
    --task-timeout=30m \
    --service-account "${JOB_SERVICE_ACCOUNT}" \
    --add-volume "name=v9-persist,type=cloud-storage,bucket=${BUCKET}" \
    --add-volume-mount "volume=v9-persist,mount-path=/mnt/v9_persist" \
    --set-env-vars "^#^GOOGLE_CLOUD_PROJECT=${PROJECT_ID}#V9_RUNTIME_MODE=cloud#V9_CLOUD_REGION=${REGION}#V9_WEEKLY_JOB_NAME=${JOB}#V9_PERSIST_BUCKET=${BUCKET}#V9_PERSIST_ROOT=${V9_PERSIST_ROOT}#V9_WEEKLY_CONFIG_OBJECT=${V9_WEEKLY_CONFIG_OBJECT}#V9_ALLOWED_RECIPIENTS=\${V9_ALLOWED_RECIPIENTS}#SMTP_HOST=\${SMTP_HOST}#SMTP_PORT=\${SMTP_PORT}#SMTP_USERNAME=\${SMTP_USERNAME}#SMTP_FROM_EMAIL=\${SMTP_FROM_EMAIL}#V9_ENABLE_EMAIL_SEND=false#DISABLE_EMAIL_SEND=true#EMAIL_SEND_MODE=preview" \
    --set-secrets "SMTP_PASSWORD=${SMTP_PASSWORD_SECRET}:latest,TAVILY_API_KEY=${TAVILY_API_KEY_SECRET}:latest"
else
  gcloud run jobs create "${JOB}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --image "${image_preview}" \
    --command python \
    --args scripts/run_v9_cloud_weekly_job.py \
    --tasks=1 \
    --parallelism=1 \
    --max-retries=0 \
    --task-timeout=30m \
    --service-account "${JOB_SERVICE_ACCOUNT}" \
    --add-volume "name=v9-persist,type=cloud-storage,bucket=${BUCKET}" \
    --add-volume-mount "volume=v9-persist,mount-path=/mnt/v9_persist" \
    --set-env-vars "^#^GOOGLE_CLOUD_PROJECT=${PROJECT_ID}#V9_RUNTIME_MODE=cloud#V9_CLOUD_REGION=${REGION}#V9_WEEKLY_JOB_NAME=${JOB}#V9_PERSIST_BUCKET=${BUCKET}#V9_PERSIST_ROOT=${V9_PERSIST_ROOT}#V9_WEEKLY_CONFIG_OBJECT=${V9_WEEKLY_CONFIG_OBJECT}#V9_ALLOWED_RECIPIENTS=\${V9_ALLOWED_RECIPIENTS}#SMTP_HOST=\${SMTP_HOST}#SMTP_PORT=\${SMTP_PORT}#SMTP_USERNAME=\${SMTP_USERNAME}#SMTP_FROM_EMAIL=\${SMTP_FROM_EMAIL}#V9_ENABLE_EMAIL_SEND=false#DISABLE_EMAIL_SEND=true#EMAIL_SEND_MODE=preview" \
    --set-secrets "SMTP_PASSWORD=${SMTP_PASSWORD_SECRET}:latest,TAVILY_API_KEY=${TAVILY_API_KEY_SECRET}:latest"
fi

## Bootstrap enabled=false settings object
python scripts/bootstrap_v9_cloud_weekly_settings.py

## Manual skip test before Scheduler
gcloud run jobs execute "${JOB}" --project "${PROJECT_ID}" --region "${REGION}" --wait

## Grant Scheduler invoker on Job
gcloud run jobs add-iam-policy-binding "${JOB}" --project "${PROJECT_ID}" --region "${REGION}" --member "serviceAccount:${SCHEDULER_SERVICE_ACCOUNT}" --role "roles/run.invoker"

## Create or update Scheduler
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

## Pause Scheduler immediately
gcloud scheduler jobs pause "${SCHEDULER_JOB}" --project "${PROJECT_ID}" --location "${REGION}"

## Verify pause state
gcloud scheduler jobs describe "${SCHEDULER_JOB}" --project "${PROJECT_ID}" --location "${REGION}" --format="value(state)"
EOF
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
  load_nonsecret_smtp_env_from_dotenv
  require_var V9_ALLOWED_RECIPIENTS
  require_var SMTP_HOST
  require_var SMTP_PORT
  require_var SMTP_USERNAME
  require_var SMTP_FROM_EMAIL
  IMAGE_URI="$(resolve_image_uri)"

  run_local_checks
  enable_required_apis
  ensure_service_account "${SERVICE_ACCOUNT}" "${SERVICE_ACCOUNT%%@*}" "Tech Cartography v9 Streamlit Service"
  ensure_service_account "${JOB_SERVICE_ACCOUNT}" "${JOB_SERVICE_ACCOUNT%%@*}" "Tech Cartography v9 Weekly Job"
  ensure_service_account "${SCHEDULER_SERVICE_ACCOUNT}" "${SCHEDULER_SERVICE_ACCOUNT%%@*}" "Tech Cartography v9 Scheduler Invoker"
  ensure_bucket
  grant_bucket_iam "${SERVICE_ACCOUNT}"
  grant_bucket_iam "${JOB_SERVICE_ACCOUNT}"
  grant_secret_iam "${SMTP_PASSWORD_SECRET}" "${JOB_SERVICE_ACCOUNT}"
  grant_secret_iam "${TAVILY_API_KEY_SECRET}" "${JOB_SERVICE_ACCOUNT}"
  build_image
  deploy_service
  grant_iap_access
  deploy_job
  bootstrap_settings
  manual_skip_test
  grant_scheduler_invoker
  deploy_scheduler
  pause_scheduler
  verify_scheduler_pause
}

main() {
  case "${MODE}" in
    --plan)
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
