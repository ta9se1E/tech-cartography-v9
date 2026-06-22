#!/usr/bin/env bash
# Safe deploy for Cloud Run live — runs checks first, preserves IAP (does not disable IAP).
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-devops-ai-agent-hackathon-2026}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-tech-cartography-v7-live}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if command -v conda >/dev/null 2>&1; then
  PY=(conda run -n "${CONDA_ENV:-2026hack}" python)
else
  PY=(python3)
fi

export PYTHONPATH="${ROOT}/src"

log() {
  printf '%s\n' "$*"
}

resolve_live_artifacts_bucket() {
  if [[ -n "${LIVE_ARTIFACTS_BUCKET:-}" ]]; then
    printf '%s\n' "${LIVE_ARTIFACTS_BUCKET}"
    return 0
  fi
  local project_number
  project_number="$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")"
  if [[ -z "${project_number}" ]]; then
    log "ERROR: could not resolve PROJECT_NUMBER for ${PROJECT_ID}"
    exit 1
  fi
  printf 'tech-cartography-v7-live-artifacts-%s\n' "${project_number}"
}

verify_live_artifacts_bucket() {
  log "Verifying live artifacts bucket: gs://${LIVE_ARTIFACTS_BUCKET}"
  if ! gcloud storage buckets describe "gs://${LIVE_ARTIFACTS_BUCKET}" >/dev/null 2>&1; then
    log "ERROR: bucket gs://${LIVE_ARTIFACTS_BUCKET} does not exist. Aborting deploy."
    exit 1
  fi
  log "Bucket exists."
}

run_python_checks() {
  log "Running compileall..."
  "${PY[@]}" -m compileall scripts src tests app.py
  log "Running pytest..."
  "${PY[@]}" -m pytest -q
  log "Running check_cloudrun_demo_ready.py..."
  "${PY[@]}" scripts/check_cloudrun_demo_ready.py
  log "Running check_live_beta_ready.py..."
  "${PY[@]}" scripts/check_live_beta_ready.py
  log "Running check_cicd_ready.py..."
  "${PY[@]}" scripts/check_cicd_ready.py
  log "Running check_iap_cutover_ready.py..."
  "${PY[@]}" scripts/check_iap_cutover_ready.py \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --service "${SERVICE}"
}

deploy_live() {
  local -a volume_args=()
  if [[ -n "${LIVE_ARTIFACTS_BUCKET}" ]]; then
    volume_args+=(
      --add-volume "name=live-artifacts,type=cloud-storage,bucket=${LIVE_ARTIFACTS_BUCKET}"
      --add-volume-mount "volume=live-artifacts,mount-path=/mnt/live_artifacts"
    )
  fi

  log "Deploying ${SERVICE} to ${REGION} (IAP preserved)..."
  gcloud run deploy "${SERVICE}" \
    --source . \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --allow-unauthenticated \
    "${volume_args[@]}" \
    --update-env-vars "REQUIRE_LOGIN=true,APP_DEFAULT_MODE=analyst,AUTH_PROVIDER_MODE=iap,IAP_JWT_VERIFY_MODE=off,SHOW_DEVELOPER_MODE=false,DEMO_OUTPUTS_ROOT=demo_outputs,LIVE_OUTPUTS_ROOT=/mnt/live_artifacts/outputs,DISABLE_EXTERNAL_API=true,DISABLE_EMAIL_SEND=true,DISABLE_SCHEDULER=true,TECH_CARTOGRAPHY_ADMIN_EMAILS=ta9se1@gmail.com" \
    --update-secrets "TAVILY_API_KEY=tech-cartography-tavily-api-key:latest,SMTP_PASSWORD=tech-cartography-smtp-password:latest"

  log "Post-deploy service summary:"
  gcloud run services describe "${SERVICE}" \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --format="table(metadata.name,status.url,status.latestReadyRevisionName)"
}

main() {
  LIVE_ARTIFACTS_BUCKET="$(resolve_live_artifacts_bucket)"
  verify_live_artifacts_bucket
  run_python_checks
  deploy_live
  log "Deploy complete."
}

main "$@"
