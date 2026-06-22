#!/usr/bin/env bash
# Emergency rollback: disable IAP and restore Basic Login (manual use only).
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-devops-ai-agent-hackathon-2026}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-tech-cartography-v7-live}"
LIVE_ARTIFACTS_BUCKET="${LIVE_ARTIFACTS_BUCKET:-tech-cartography-v7-live-artifacts-${PROJECT_ID}}"

log() {
  printf '%s\n' "$*"
}

prompt_password() {
  log "Set fallback admin login password, then press Enter:"
  read -rs TC_LOGIN_PASSWORD
  echo
  if [[ -z "${TC_LOGIN_PASSWORD}" ]]; then
    log "ERROR: password must not be empty."
    exit 1
  fi
}

main() {
  prompt_password

  log "Disabling IAP on ${SERVICE}..."
  gcloud run services update "${SERVICE}" \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --no-iap

  local -a volume_args=()
  if [[ -n "${LIVE_ARTIFACTS_BUCKET}" ]]; then
    volume_args+=(
      --add-volume "name=live-artifacts,type=cloud-storage,bucket=${LIVE_ARTIFACTS_BUCKET}"
      --add-volume-mount "volume=live-artifacts,mount-path=/mnt/live_artifacts"
    )
  fi

  log "Restoring Basic Login env (AUTH_PROVIDER_MODE=basic)..."
  gcloud run services update "${SERVICE}" \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    "${volume_args[@]}" \
    --update-env-vars "AUTH_PROVIDER_MODE=basic,REQUIRE_LOGIN=true,TECH_CARTOGRAPHY_LOGIN_USERNAME=admin,TECH_CARTOGRAPHY_LOGIN_PASSWORD=${TC_LOGIN_PASSWORD},LIVE_OUTPUTS_ROOT=/mnt/live_artifacts/outputs,DISABLE_EXTERNAL_API=true,DISABLE_EMAIL_SEND=true,DISABLE_SCHEDULER=true,ENABLE_APPROVED_MEMBER_SEND=false,APPROVED_MEMBER_SEND_CONFIRMATION=SEND TO APPROVED MEMBER"

  unset TC_LOGIN_PASSWORD

  log "Rollback deploy summary:"
  gcloud run services describe "${SERVICE}" \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --format="table(metadata.name,status.url,status.latestReadyRevisionName)"
  log "Verify Basic Login, Run History, and LIVE_OUTPUTS_ROOT mount."
}

main "$@"
