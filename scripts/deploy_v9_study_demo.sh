#!/usr/bin/env bash
# Plan/apply deploy helper for the isolated Tech Cartography v9 study demo service.
set -euo pipefail

MODE="${1:---plan}"
PROJECT_ID="${PROJECT_ID:-devops-ai-agent-hackathon-2026}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-tech-cartography-v9-study-demo}"
BUCKET="${BUCKET:-tech-cartography-v9-study-demo-1020686343587}"
ARTIFACT_REPO="${ARTIFACT_REPO:-cloud-run-source-deploy}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-tech-cartography-v9-study-demo@devops-ai-agent-hackathon-2026.iam.gserviceaccount.com}"
PASSWORD_SECRET="${PASSWORD_SECRET:-tech-cartography-v9-study-demo-password}"
PASSWORD_SECRET_VERSION="${PASSWORD_SECRET_VERSION:-2}"
OPENALEX_SECRET="${OPENALEX_SECRET:-tech-cartography-v9-study-demo-openalex-api-key}"
OPENALEX_SECRET_VERSION="${OPENALEX_SECRET_VERSION:-1}"
TAVILY_SECRET="${TAVILY_SECRET:-tech-cartography-v9-study-demo-tavily-api-key}"
TAVILY_SECRET_VERSION="${TAVILY_SECRET_VERSION:-1}"
STUDY_DEMO_EXPIRES_AT="${STUDY_DEMO_EXPIRES_AT:-2026-07-11T19:27:30Z}"
V9_UI_MODE="${V9_UI_MODE:-simple}"
V9_PERSIST_ROOT="${V9_PERSIST_ROOT:-/mnt/v9_study_demo/active}"
BUILD_ID=""
SOURCE_BUCKET=""
SOURCE_OBJECT=""
CLEANUP_RESULT="not_started"
IMAGE_URI=""
IMAGE_DIGEST=""
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

ALLOWED_SERVICES=("tech-cartography-v9-study-demo")

if [[ -x "/opt/miniconda3/envs/${CONDA_ENV:-2026hack}/bin/python" ]]; then
  PY=("/opt/miniconda3/envs/${CONDA_ENV:-2026hack}/bin/python")
elif command -v conda >/dev/null 2>&1; then
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
  scripts/deploy_v9_study_demo.sh --plan
  V9_STUDY_DEMO_DEPLOY_APPROVED=true scripts/deploy_v9_study_demo.sh --apply

Stage A defaults to --plan only. This script never modifies production resources.
EOF
}

assert_allowed_service() {
  local allowed=0
  local name
  for name in "${ALLOWED_SERVICES[@]}"; do
    if [[ "${SERVICE}" == "${name}" ]]; then
      allowed=1
      break
    fi
  done
  if [[ "${allowed}" -ne 1 ]]; then
    log "ERROR: SERVICE must be one of: ${ALLOWED_SERVICES[*]}"
    exit 1
  fi
}

require_apply_guard() {
  if [[ "${V9_STUDY_DEMO_DEPLOY_APPROVED:-false}" != "true" ]]; then
    log "ERROR: --apply requires V9_STUDY_DEMO_DEPLOY_APPROVED=true"
    exit 1
  fi
}

run_local_checks() {
  "${PY[@]}" -m compileall services_v9 scripts ui_v9 tests app.py
  shopt -s nullglob
  local test_files=(tests/test_v9_*.py)
  PYTHONPATH=.:src "${PY[@]}" -m pytest "${test_files[@]}" -q
  "${PY[@]}" scripts/check_v9_study_demo_readiness.py
  "${PY[@]}" scripts/check_v9_build_context.py --ignore-file .gcloudignore
}

print_plan() {
  assert_allowed_service
  cat <<EOF
{
  "status": "plan",
  "service": "${SERVICE}",
  "region": "${REGION}",
  "project_id": "${PROJECT_ID}",
  "bucket": "${BUCKET}",
  "service_account": "${SERVICE_ACCOUNT}",
  "password_secret": "${PASSWORD_SECRET}:${PASSWORD_SECRET_VERSION}",
  "openalex_secret": "${OPENALEX_SECRET}:${OPENALEX_SECRET_VERSION}",
  "tavily_secret": "${TAVILY_SECRET}:${TAVILY_SECRET_VERSION}",
  "expires_at_utc": "${STUDY_DEMO_EXPIRES_AT}",
  "min_instances": 0,
  "max_instances": 1,
  "scheduler": "none",
  "cloud_run_job": "none",
  "public_service": "${SERVICE} only",
  "production_resources_modified": false,
  "env": {
    "V9_UI_MODE": "${V9_UI_MODE}",
    "V9_STUDY_DEMO_MODE": "true",
    "V9_STUDY_DEMO_BUCKET": "${BUCKET}",
    "V9_STUDY_DEMO_DISABLE_EXTERNAL_EXECUTION": "true",
    "V9_STUDY_DEMO_SHARED_STATE": "true",
    "V9_ENABLE_EMAIL_SEND": "false",
    "DISABLE_EMAIL_SEND": "true",
    "EMAIL_SEND_MODE": "preview",
    "V9_CLOUD_ENABLE_PATENT": "true",
    "V9_CLOUD_ENABLE_PAPER": "true",
    "V9_CLOUD_ENABLE_WEB_COMPANY": "true",
    "V9_CLOUD_GOOGLE_GROUNDING": "false",
    "V9_STUDY_DEMO_SEARCH_ENABLED": "true",
    "V9_STUDY_DEMO_ENABLE_PATENT_SEARCH": "true",
    "V9_STUDY_DEMO_ENABLE_PAPER_SEARCH": "true",
    "V9_STUDY_DEMO_ENABLE_WEB_SEARCH": "true",
    "V9_STUDY_DEMO_BIGQUERY_DRY_RUN_FIRST": "true",
    "V9_STUDY_DEMO_BIGQUERY_MAX_BYTES_BILLED": "2199023255552"
  },
  "rollback_revision": "tech-cartography-v9-study-demo-00001-b48",
  "iam_plan_stage_c2": [
    "roles/bigquery.jobUser on project (demo SA only)",
    "roles/storage.objectAdmin on demo bucket",
    "secretAccessor on demo password/openalex/tavily secrets"
  ],
  "apply_guard": "V9_STUDY_DEMO_DEPLOY_APPROVED=true",
  "notes": [
    "V9_STUDY_DEMO_EXPIRES_AT is set at deploy time to UTC+7days",
    "seed data is copied separately via prepare_v9_study_demo_seed.py",
    "Cloud Run mounts demo bucket at /mnt/v9_study_demo with active/ prefix"
  ]
}
EOF
}

assert_password_secret_ready() {
  local version_state
  version_state="$(gcloud secrets versions describe "${PASSWORD_SECRET_VERSION}" \
    --secret="${PASSWORD_SECRET}" \
    --project="${PROJECT_ID}" \
    --format='value(state)' 2>/dev/null || true)"
  if [[ "${version_state}" != "ENABLED" ]]; then
    log "ERROR: password secret ${PASSWORD_SECRET}:${PASSWORD_SECRET_VERSION} is not ENABLED"
    exit 1
  fi
}

assert_openalex_secret_ready() {
  local version_state
  version_state="$(gcloud secrets versions describe "${OPENALEX_SECRET_VERSION}" \
    --secret="${OPENALEX_SECRET}" \
    --project="${PROJECT_ID}" \
    --format='value(state)' 2>/dev/null || true)"
  if [[ "${version_state}" != "ENABLED" ]]; then
    log "ERROR: openalex secret ${OPENALEX_SECRET}:${OPENALEX_SECRET_VERSION} is not ENABLED"
    exit 1
  fi
}

assert_tavily_secret_ready() {
  local version_state
  version_state="$(gcloud secrets versions describe "${TAVILY_SECRET_VERSION}" \
    --secret="${TAVILY_SECRET}" \
    --project="${PROJECT_ID}" \
    --format='value(state)' 2>/dev/null || true)"
  if [[ "${version_state}" != "ENABLED" ]]; then
    log "ERROR: tavily secret ${TAVILY_SECRET}:${TAVILY_SECRET_VERSION} is not ENABLED"
    exit 1
  fi
}

compute_expiry_utc() {
  printf '%s' "${STUDY_DEMO_EXPIRES_AT}"
}

compute_expiry_jst() {
  local expiry_utc="$1"
  EXPIRY_UTC="${expiry_utc}" "${PY[@]}" - <<'PY'
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
raw = os.environ["EXPIRY_UTC"].replace("Z", "+00:00")
parsed = datetime.fromisoformat(raw)
print(parsed.astimezone(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S JST"))
PY
}

wait_for_build() {
  local status=""
  while true; do
    status="$(gcloud builds describe "${BUILD_ID}" --project "${PROJECT_ID}" --region "${REGION}" --format='value(status)')"
    case "${status}" in
      QUEUED|WORKING|PENDING)
        sleep 5
        ;;
      *)
        printf '%s' "${status}"
        return 0
        ;;
    esac
  done
}

cleanup_build_source_archive() {
  if [[ -z "${BUILD_ID}" ]]; then
    CLEANUP_RESULT="skipped_no_build"
    return 0
  fi
  local build_json export_lines
  build_json="$(gcloud builds describe "${BUILD_ID}" --project "${PROJECT_ID}" --region "${REGION}" --format=json)"
  export_lines="$(printf '%s' "${build_json}" | "${PY[@]}" -c "
import json
import shlex
import sys
from scripts.v9_build_security import build_source_cleanup_target
payload = json.load(sys.stdin)
target = build_source_cleanup_target(payload)
print(f\"SOURCE_BUCKET={shlex.quote(str(target.get('bucket', '') or ''))}\")
print(f\"SOURCE_OBJECT={shlex.quote(str(target.get('object', '') or ''))}\")
print(f\"SOURCE_TARGET_STATUS={shlex.quote(str(target.get('status', '') or ''))}\")
print(f\"SOURCE_TARGET_REASON={shlex.quote(str(target.get('reason', '') or ''))}\")
")"
  eval "${export_lines}"
  if [[ "${SOURCE_TARGET_STATUS:-}" != "ok" || -z "${SOURCE_BUCKET}" || -z "${SOURCE_OBJECT}" ]]; then
    CLEANUP_RESULT="skipped_${SOURCE_TARGET_REASON:-invalid_target}"
    return 0
  fi
  if gcloud storage rm "gs://${SOURCE_BUCKET}/${SOURCE_OBJECT}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    CLEANUP_RESULT="deleted"
  else
    CLEANUP_RESULT="delete_failed"
  fi
}

build_study_demo_image() {
  local git_sha image_uri build_status
  git_sha="$(git rev-parse --short HEAD)"
  image_uri="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/${SERVICE}:${git_sha}"
  BUILD_ID="$(gcloud builds submit . \
    --async \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --ignore-file=.gcloudignore \
    --config cloudbuild.v9.yaml \
    --substitutions "_IMAGE_URI=${image_uri}" \
    --format='value(id)')"
  if [[ -z "${BUILD_ID}" ]]; then
    log "ERROR: failed to obtain Cloud Build ID"
    exit 1
  fi
  build_status="$(wait_for_build)"
  if [[ "${build_status}" != "SUCCESS" ]]; then
    log "ERROR: Cloud Build ${BUILD_ID} failed with status ${build_status}"
    exit 1
  fi
  IMAGE_URI="${image_uri}"
  IMAGE_DIGEST="$(gcloud builds describe "${BUILD_ID}" --project "${PROJECT_ID}" --region "${REGION}" --format=json | "${PY[@]}" -c "
import json, sys
payload = json.load(sys.stdin)
images = payload.get('results', {}).get('images', []) or []
for item in images:
  if isinstance(item, dict) and item.get('digest'):
    print(item['digest'])
    break
")"
}

deploy_private_service() {
  local expiry_utc="$1"
  gcloud run deploy "${SERVICE}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --image "${IMAGE_URI}" \
    --service-account "${SERVICE_ACCOUNT}" \
    --min-instances 0 \
    --max-instances 1 \
    --no-allow-unauthenticated \
    --add-volume "name=v9-study-demo,type=cloud-storage,bucket=${BUCKET}" \
    --add-volume-mount "volume=v9-study-demo,mount-path=/mnt/v9_study_demo" \
    --set-secrets "V9_STUDY_DEMO_PASSWORD=${PASSWORD_SECRET}:${PASSWORD_SECRET_VERSION},V9_STUDY_DEMO_OPENALEX_API_KEY=${OPENALEX_SECRET}:${OPENALEX_SECRET_VERSION},V9_STUDY_DEMO_TAVILY_API_KEY=${TAVILY_SECRET}:${TAVILY_SECRET_VERSION}" \
    --set-env-vars "^#^GOOGLE_CLOUD_PROJECT=${PROJECT_ID}#V9_RUNTIME_MODE=cloud#V9_CLOUD_REGION=${REGION}#V9_PERSIST_BUCKET=${BUCKET}#V9_PERSIST_ROOT=${V9_PERSIST_ROOT}#V9_WEEKLY_CONFIG_OBJECT=active/v9_config/weekly_delivery_config.json#V9_UI_MODE=${V9_UI_MODE}#V9_STUDY_DEMO_MODE=true#V9_STUDY_DEMO_BUCKET=${BUCKET}#V9_STUDY_DEMO_EXPIRES_AT=${expiry_utc}#V9_STUDY_DEMO_DISABLE_EXTERNAL_EXECUTION=true#V9_STUDY_DEMO_SHARED_STATE=true#V9_ENABLE_EMAIL_SEND=false#DISABLE_EMAIL_SEND=true#EMAIL_SEND_MODE=preview#V9_CLOUD_ENABLE_PATENT=true#V9_CLOUD_ENABLE_PAPER=true#V9_CLOUD_ENABLE_WEB_COMPANY=true#V9_CLOUD_GOOGLE_GROUNDING=false#V9_STUDY_DEMO_SEARCH_ENABLED=true#V9_STUDY_DEMO_ENABLE_PATENT_SEARCH=true#V9_STUDY_DEMO_ENABLE_PAPER_SEARCH=true#V9_STUDY_DEMO_ENABLE_WEB_SEARCH=true#V9_STUDY_DEMO_BIGQUERY_DRY_RUN_FIRST=true#V9_STUDY_DEMO_BIGQUERY_MAX_BYTES_BILLED=2199023255552#V9_STUDY_DEMO_BIGQUERY_PRICE_PER_TIB_USD=6.25#V9_ENABLE_CLOUD_SCHEDULER_ADMIN=false"
}

smoke_test_authenticated() {
  local url="$1"
  local token body
  token="$(gcloud auth print-identity-token 2>/dev/null || true)"
  if [[ -z "${token}" ]]; then
    log "WARN: identity token unavailable; skipping authenticated smoke test body check"
    return 0
  fi
  body="$(curl -fsS -H "Authorization: Bearer ${token}" "${url}" || true)"
  if [[ -z "${body}" ]]; then
    log "ERROR: authenticated smoke test returned empty body"
    exit 1
  fi
  if ! grep -q "Streamlit" <<<"${body}"; then
    log "ERROR: authenticated smoke test did not detect Streamlit bootstrap"
    exit 1
  fi
}

publicize_service() {
  gcloud run services add-iam-policy-binding "${SERVICE}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --member="allUsers" \
    --role="roles/run.invoker" \
    --quiet
}

verify_public_password_gate() {
  local url="$1"
  local code body
  code="$(curl -sS -o /tmp/v9_study_demo_public.html -w '%{http_code}' "${url}" || true)"
  body="$(cat /tmp/v9_study_demo_public.html 2>/dev/null || true)"
  rm -f /tmp/v9_study_demo_public.html
  if [[ "${code}" != "200" ]]; then
    log "ERROR: public smoke test HTTP ${code}"
    exit 1
  fi
  if ! grep -qi "streamlit" <<<"${body}"; then
    log "ERROR: public smoke test did not detect Streamlit bootstrap"
    exit 1
  fi
}

apply_deploy() {
  require_apply_guard
  assert_allowed_service
  run_local_checks
  assert_password_secret_ready
  assert_openalex_secret_ready
  assert_tavily_secret_ready

  local expiry_utc expiry_jst deploy_time_utc deploy_time_jst service_url revision
  expiry_utc="$(compute_expiry_utc)"
  expiry_jst="$(compute_expiry_jst "${expiry_utc}")"
  deploy_time_utc="$("${PY[@]}" - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
PY
)"
  deploy_time_jst="$(compute_expiry_jst "${deploy_time_utc}")"

  build_study_demo_image
  cleanup_build_source_archive
  deploy_private_service "${expiry_utc}"

  service_url="$(gcloud run services describe "${SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --format='value(status.url)')"
  revision="$(gcloud run services describe "${SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --format='value(status.latestReadyRevisionName)')"
  smoke_test_authenticated "${service_url}"
  publicize_service
  verify_public_password_gate "${service_url}"

  cat <<EOF
{
  "status": "deployed",
  "service": "${SERVICE}",
  "service_url": "${service_url}",
  "revision": "${revision}",
  "project_id": "${PROJECT_ID}",
  "region": "${REGION}",
  "image_uri": "${IMAGE_URI}",
  "image_digest": "${IMAGE_DIGEST:-}",
  "build_id": "${BUILD_ID}",
  "build_source_cleanup": "${CLEANUP_RESULT}",
  "service_account": "${SERVICE_ACCOUNT}",
  "bucket": "${BUCKET}",
  "password_secret": "${PASSWORD_SECRET}:${PASSWORD_SECRET_VERSION}",
  "openalex_secret": "${OPENALEX_SECRET}:${OPENALEX_SECRET_VERSION}",
  "tavily_secret": "${TAVILY_SECRET}:${TAVILY_SECRET_VERSION}",
  "expires_at_utc": "${expiry_utc}",
  "expires_at_jst": "${expiry_jst}",
  "deployed_at_utc": "${deploy_time_utc}",
  "deployed_at_jst": "${deploy_time_jst}",
  "min_instances": 0,
  "max_instances": 1,
  "public_method": "allUsers roles/run.invoker",
  "production_resources_modified": false
}
EOF
}

case "${MODE}" in
  --plan)
    run_local_checks
    print_plan
    ;;
  --apply)
    apply_deploy
    ;;
  *)
    usage
    exit 1
    ;;
esac
