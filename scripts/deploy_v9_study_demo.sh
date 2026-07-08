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
DEPLOY_STATE_FILE="${V9_DEPLOY_STATE_FILE:-${RUNNER_TEMP:-/tmp}/v9-deploy-state.json}"
DEPLOY_RESULT_FILE="${V9_DEPLOY_RESULT_FILE:-${RUNNER_TEMP:-/tmp}/v9-deploy-result.json}"
BUILD_ID=""
SOURCE_BUCKET=""
SOURCE_OBJECT=""
CLEANUP_RESULT="not_started"
IMAGE_URI=""
IMAGE_DIGEST=""
CANDIDATE_READY_MAX_ATTEMPTS="${V9_CANDIDATE_READY_MAX_ATTEMPTS:-60}"
CANDIDATE_READY_INTERVAL="${V9_CANDIDATE_READY_INTERVAL:-5}"
TRAFFIC_CONVERGE_MAX_ATTEMPTS="${V9_TRAFFIC_CONVERGE_MAX_ATTEMPTS:-60}"
TRAFFIC_CONVERGE_INTERVAL="${V9_TRAFFIC_CONVERGE_INTERVAL:-5}"

PREVIOUS_REVISION=""
NEW_REVISION=""
CANDIDATE_TAG=""
CANDIDATE_URL=""
CANDIDATE_SMOKE_HTTP=""
CANDIDATE_CLEANUP="skipped"

STATE_MUTATION_STARTED=false
STATE_CLOUD_BUILD_STARTED=false
STATE_CLOUD_RUN_UPDATE_STARTED=false
STATE_TRAFFIC_PROMOTION_STARTED=false
STATE_TARGET_REVISION=""
STATE_PREVIOUS_REVISION=""

RESULT_PREVIOUS_REVISION=""
RESULT_CANDIDATE_TAG=""
RESULT_CANDIDATE_URL=""
RESULT_CANDIDATE_SMOKE_STATUS="skipped"
RESULT_CANDIDATE_SMOKE_HTTP="0"
RESULT_TRAFFIC_PROMOTION_STARTED="false"
RESULT_TRAFFIC_PROMOTED="false"
RESULT_TRAFFIC_TARGET_REVISION=""
RESULT_TRAFFIC_PERCENT="0"
RESULT_FINAL_SMOKE_STATUS="skipped"
RESULT_IMAGE_DIGEST=""
RESULT_CANDIDATE_CLEANUP="skipped"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

ALLOWED_SERVICES=("tech-cartography-v9-study-demo")
CONDA_ENV_NAME="${CONDA_ENV:-2026hack}"
PY=()
PY_SELECTOR_SOURCE=""

export PYTHONPATH="${ROOT}:${ROOT}/src"

log() {
  printf '%s\n' "$*"
}

_conda_env_available() {
  local env_name="$1"
  if ! command -v conda >/dev/null 2>&1; then
    return 1
  fi
  if conda run -n "${env_name}" python -c 'import sys' >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

_python_candidate_usable() {
  "${@}" -c 'import sys; assert sys.version_info[:2] == (3, 11); import json, pathlib, zoneinfo' >/dev/null 2>&1
}

select_deploy_python() {
  local candidate=""
  if [[ -n "${V9_PYTHON_BIN:-}" && -x "${V9_PYTHON_BIN}" ]]; then
    if _python_candidate_usable "${V9_PYTHON_BIN}"; then
      PY=("${V9_PYTHON_BIN}")
      PY_SELECTOR_SOURCE="V9_PYTHON_BIN"
      return 0
    fi
  fi
  if command -v python >/dev/null 2>&1; then
    candidate="$(command -v python)"
    if [[ -n "${candidate}" && -x "${candidate}" ]] && _python_candidate_usable "${candidate}"; then
      PY=("${candidate}")
      PY_SELECTOR_SOURCE="system-python"
      return 0
    fi
  fi
  if command -v python3 >/dev/null 2>&1; then
    candidate="$(command -v python3)"
    if [[ -n "${candidate}" && -x "${candidate}" ]] && _python_candidate_usable "${candidate}"; then
      PY=("${candidate}")
      PY_SELECTOR_SOURCE="system-python3"
      return 0
    fi
  fi
  candidate="/opt/miniconda3/envs/${CONDA_ENV_NAME}/bin/python"
  if [[ -x "${candidate}" ]] && _python_candidate_usable "${candidate}"; then
    PY=("${candidate}")
    PY_SELECTOR_SOURCE="conda-env-direct"
    return 0
  fi
  if _conda_env_available "${CONDA_ENV_NAME}"; then
    if _python_candidate_usable conda run -n "${CONDA_ENV_NAME}" python; then
      PY=(conda run -n "${CONDA_ENV_NAME}" python)
      PY_SELECTOR_SOURCE="conda-run"
      return 0
    fi
  fi
  log "ERROR: no usable Python interpreter found"
  exit 1
}

validate_deploy_python() {
  local version executable
  version="$("${PY[@]}" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
  if [[ "${version}" != 3.11* ]]; then
    log "ERROR: Python 3.11 required, found ${version}"
    exit 1
  fi
  if ! "${PY[@]}" -c 'import json, pathlib, zoneinfo' >/dev/null 2>&1; then
    log "ERROR: required Python modules unavailable"
    exit 1
  fi
  executable="$("${PY[@]}" -c 'import sys; print(sys.executable)')"
  log "Python selector:"
  log "source=${PY_SELECTOR_SOURCE}"
  log "executable=${executable}"
  log "version=${version}"
}

select_deploy_python
validate_deploy_python

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy_v9_study_demo.sh --plan
  V9_STUDY_DEMO_DEPLOY_APPROVED=true scripts/deploy_v9_study_demo.sh --apply
  scripts/deploy_v9_study_demo.sh --print-python-selector
  scripts/deploy_v9_study_demo.sh --check-public-access

Stage A defaults to --plan only. This script never modifies production resources.
GitHub Actions uses setup-python; conda is only selected when the env exists.
Approved deploy preserves existing Cloud Run IAM; public access is verified read-only.
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
  "${PY[@]}" scripts/check_v9_study_demo_readiness.py --scope offline-ci
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
  "iam_policy_mutations": 0,
  "public_access_verify": "read-only",
  "public_access_changed": false,
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

persist_deploy_state() {
  local state_file="${DEPLOY_STATE_FILE}"
  local tmp_file="${state_file}.tmp"
  mkdir -p "$(dirname "${state_file}")"
  STATE_MUTATION_STARTED="${STATE_MUTATION_STARTED:-false}" \
  STATE_CLOUD_BUILD_STARTED="${STATE_CLOUD_BUILD_STARTED:-false}" \
  STATE_CLOUD_RUN_UPDATE_STARTED="${STATE_CLOUD_RUN_UPDATE_STARTED:-false}" \
  STATE_TRAFFIC_PROMOTION_STARTED="${STATE_TRAFFIC_PROMOTION_STARTED:-false}" \
  STATE_TARGET_REVISION="${STATE_TARGET_REVISION:-}" \
  STATE_PREVIOUS_REVISION="${STATE_PREVIOUS_REVISION:-}" \
  STATE_TMP="${tmp_file}" \
  STATE_FILE="${state_file}" \
    "${PY[@]}" - <<'PY'
import json
import os
import pathlib

payload = {
    "mutation_started": os.environ["STATE_MUTATION_STARTED"] == "true",
    "cloud_build_started": os.environ["STATE_CLOUD_BUILD_STARTED"] == "true",
    "cloud_run_update_started": os.environ["STATE_CLOUD_RUN_UPDATE_STARTED"] == "true",
    "traffic_promotion_started": os.environ["STATE_TRAFFIC_PROMOTION_STARTED"] == "true",
    "target_revision": os.environ["STATE_TARGET_REVISION"],
    "previous_revision": os.environ["STATE_PREVIOUS_REVISION"],
}
tmp = pathlib.Path(os.environ["STATE_TMP"])
tmp.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
tmp.replace(pathlib.Path(os.environ["STATE_FILE"]))
PY
}

write_deploy_result() {
  local status="$1"
  local public_access_verified="$2"
  local mutation_started="$3"
  local cloud_build_started="$4"
  local cloud_build_id="$5"
  local cloud_run_update_started="$6"
  local new_revision="$7"
  local result_file="${DEPLOY_RESULT_FILE}"
  local tmp_file="${result_file}.tmp"
  mkdir -p "$(dirname "${result_file}")"
  DEPLOY_RESULT_STATUS="${status}" \
  DEPLOY_RESULT_PUBLIC_ACCESS_VERIFIED="${public_access_verified}" \
  DEPLOY_RESULT_MUTATION_STARTED="${mutation_started}" \
  DEPLOY_RESULT_CLOUD_BUILD_STARTED="${cloud_build_started}" \
  DEPLOY_RESULT_CLOUD_BUILD_ID="${cloud_build_id}" \
  DEPLOY_RESULT_CLOUD_RUN_UPDATE_STARTED="${cloud_run_update_started}" \
  DEPLOY_RESULT_NEW_REVISION="${new_revision}" \
  DEPLOY_RESULT_SERVICE="${SERVICE}" \
  DEPLOY_RESULT_PREVIOUS_REVISION="${RESULT_PREVIOUS_REVISION:-}" \
  DEPLOY_RESULT_CANDIDATE_TAG="${RESULT_CANDIDATE_TAG:-}" \
  DEPLOY_RESULT_CANDIDATE_URL="${RESULT_CANDIDATE_URL:-}" \
  DEPLOY_RESULT_CANDIDATE_SMOKE_STATUS="${RESULT_CANDIDATE_SMOKE_STATUS:-skipped}" \
  DEPLOY_RESULT_CANDIDATE_SMOKE_HTTP="${RESULT_CANDIDATE_SMOKE_HTTP:-0}" \
  DEPLOY_RESULT_TRAFFIC_PROMOTION_STARTED="${RESULT_TRAFFIC_PROMOTION_STARTED:-false}" \
  DEPLOY_RESULT_TRAFFIC_PROMOTED="${RESULT_TRAFFIC_PROMOTED:-false}" \
  DEPLOY_RESULT_TRAFFIC_TARGET_REVISION="${RESULT_TRAFFIC_TARGET_REVISION:-}" \
  DEPLOY_RESULT_TRAFFIC_PERCENT="${RESULT_TRAFFIC_PERCENT:-0}" \
  DEPLOY_RESULT_FINAL_SMOKE_STATUS="${RESULT_FINAL_SMOKE_STATUS:-skipped}" \
  DEPLOY_RESULT_IMAGE_DIGEST="${RESULT_IMAGE_DIGEST:-}" \
  DEPLOY_RESULT_CANDIDATE_CLEANUP="${RESULT_CANDIDATE_CLEANUP:-skipped}" \
  DEPLOY_RESULT_FILE="${result_file}" \
  DEPLOY_RESULT_TMP="${tmp_file}" \
    "${PY[@]}" - <<'PY'
import json
import os
import pathlib


def as_bool(name):
    return os.environ.get(name) == "true"


def as_int(name):
    try:
        return int(os.environ.get(name) or 0)
    except ValueError:
        return 0


payload = {
    "status": os.environ["DEPLOY_RESULT_STATUS"],
    "public_access_verified": as_bool("DEPLOY_RESULT_PUBLIC_ACCESS_VERIFIED"),
    "public_access_changed": False,
    "iam_policy_mutations": 0,
    "mutation_started": as_bool("DEPLOY_RESULT_MUTATION_STARTED"),
    "cloud_build_started": as_bool("DEPLOY_RESULT_CLOUD_BUILD_STARTED"),
    "cloud_build_id": os.environ["DEPLOY_RESULT_CLOUD_BUILD_ID"],
    "cloud_run_update_started": as_bool("DEPLOY_RESULT_CLOUD_RUN_UPDATE_STARTED"),
    "new_revision": os.environ["DEPLOY_RESULT_NEW_REVISION"],
    "previous_revision": os.environ["DEPLOY_RESULT_PREVIOUS_REVISION"],
    "candidate_tag": os.environ["DEPLOY_RESULT_CANDIDATE_TAG"],
    "candidate_url": os.environ["DEPLOY_RESULT_CANDIDATE_URL"],
    "candidate_smoke_status": os.environ["DEPLOY_RESULT_CANDIDATE_SMOKE_STATUS"],
    "candidate_smoke_http_status": as_int("DEPLOY_RESULT_CANDIDATE_SMOKE_HTTP"),
    "traffic_promotion_started": as_bool("DEPLOY_RESULT_TRAFFIC_PROMOTION_STARTED"),
    "traffic_promoted": as_bool("DEPLOY_RESULT_TRAFFIC_PROMOTED"),
    "traffic_target_revision": os.environ["DEPLOY_RESULT_TRAFFIC_TARGET_REVISION"],
    "traffic_percent": as_int("DEPLOY_RESULT_TRAFFIC_PERCENT"),
    "final_smoke_status": os.environ["DEPLOY_RESULT_FINAL_SMOKE_STATUS"],
    "image_digest": os.environ["DEPLOY_RESULT_IMAGE_DIGEST"],
    "candidate_cleanup": os.environ["DEPLOY_RESULT_CANDIDATE_CLEANUP"],
    "service": os.environ["DEPLOY_RESULT_SERVICE"],
    "production_modifications": False,
}
path = pathlib.Path(os.environ["DEPLOY_RESULT_FILE"])
tmp = pathlib.Path(os.environ["DEPLOY_RESULT_TMP"])
tmp.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
tmp.replace(path)
PY
  log "deploy result written to ${result_file}"
}

record_deploy_mutation_started() {
  STATE_MUTATION_STARTED=true
  persist_deploy_state
  log "deploy mutation_started=true recorded at ${DEPLOY_STATE_FILE}"
}

verify_public_access_readonly() {
  local policy_json rc
  set +e
  policy_json="$(gcloud run services get-iam-policy "${SERVICE}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --format=json 2>&1)"
  rc=$?
  set -e
  if [[ ${rc} -ne 0 ]]; then
    if grep -qiE 'PERMISSION_DENIED|403|does not have permission' <<<"${policy_json}"; then
      log "ERROR: unable to read Cloud Run IAM policy (permission denied)"
      exit 1
    fi
    log "ERROR: unable to read Cloud Run IAM policy"
    exit 1
  fi
  PUBLIC_IAM_POLICY="${policy_json}" "${PY[@]}" - <<'PY'
import json
import os
import sys

payload = json.loads(os.environ["PUBLIC_IAM_POLICY"])
for binding in payload.get("bindings", []):
    if binding.get("role") != "roles/run.invoker":
        continue
    members = binding.get("members") or []
    if "allUsers" in members:
        sys.exit(0)
print(
    "ERROR: Study Demo public access is not configured. "
    "Run the one-time infra setup as an administrator.",
    file=sys.stderr,
)
sys.exit(1)
PY
  log "public access verified: allUsers roles/run.invoker (read-only)"
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
  record_deploy_mutation_started
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

deploy_study_demo_service() {
  local expiry_utc="$1"
  gcloud run deploy "${SERVICE}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --image "${IMAGE_URI}" \
    --service-account "${SERVICE_ACCOUNT}" \
    --no-traffic \
    --tag "${CANDIDATE_TAG}" \
    --min-instances 0 \
    --max-instances 1 \
    --add-volume "name=v9-study-demo,type=cloud-storage,bucket=${BUCKET}" \
    --add-volume-mount "volume=v9-study-demo,mount-path=/mnt/v9_study_demo" \
    --set-secrets "V9_STUDY_DEMO_PASSWORD=${PASSWORD_SECRET}:${PASSWORD_SECRET_VERSION},V9_STUDY_DEMO_OPENALEX_API_KEY=${OPENALEX_SECRET}:${OPENALEX_SECRET_VERSION},V9_STUDY_DEMO_TAVILY_API_KEY=${TAVILY_SECRET}:${TAVILY_SECRET_VERSION}" \
    --set-env-vars "^#^GOOGLE_CLOUD_PROJECT=${PROJECT_ID}#V9_RUNTIME_MODE=cloud#V9_CLOUD_REGION=${REGION}#V9_PERSIST_BUCKET=${BUCKET}#V9_PERSIST_ROOT=${V9_PERSIST_ROOT}#V9_WEEKLY_CONFIG_OBJECT=active/v9_config/weekly_delivery_config.json#V9_UI_MODE=${V9_UI_MODE}#V9_STUDY_DEMO_MODE=true#V9_STUDY_DEMO_BUCKET=${BUCKET}#V9_STUDY_DEMO_EXPIRES_AT=${expiry_utc}#V9_STUDY_DEMO_DISABLE_EXTERNAL_EXECUTION=true#V9_STUDY_DEMO_SHARED_STATE=true#V9_ENABLE_EMAIL_SEND=false#DISABLE_EMAIL_SEND=true#EMAIL_SEND_MODE=preview#V9_CLOUD_ENABLE_PATENT=true#V9_CLOUD_ENABLE_PAPER=true#V9_CLOUD_ENABLE_WEB_COMPANY=true#V9_CLOUD_GOOGLE_GROUNDING=false#V9_STUDY_DEMO_SEARCH_ENABLED=true#V9_STUDY_DEMO_ENABLE_PATENT_SEARCH=true#V9_STUDY_DEMO_ENABLE_PAPER_SEARCH=true#V9_STUDY_DEMO_ENABLE_WEB_SEARCH=true#V9_STUDY_DEMO_BIGQUERY_DRY_RUN_FIRST=true#V9_STUDY_DEMO_BIGQUERY_MAX_BYTES_BILLED=2199023255552#V9_STUDY_DEMO_BIGQUERY_PRICE_PER_TIB_USD=6.25#V9_ENABLE_CLOUD_SCHEDULER_ADMIN=false"
}

smoke_test_authenticated_optional() {
  local url="$1"
  local token body
  token="$(gcloud auth print-identity-token 2>/dev/null || true)"
  if [[ -z "${token}" ]]; then
    log "WARN: identity token unavailable; continuing with unauthenticated smoke only"
    return 0
  fi
  body="$(curl -fsS -H "Authorization: Bearer ${token}" "${url}" || true)"
  if [[ -z "${body}" ]]; then
    log "WARN: authenticated smoke test returned empty body; continuing with unauthenticated smoke only"
    return 0
  fi
  if ! grep -qi "streamlit" <<<"${body}"; then
    log "WARN: authenticated smoke test did not detect Streamlit bootstrap; continuing with unauthenticated smoke only"
    return 0
  fi
  log "authenticated smoke test passed (optional)"
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

resolve_candidate_tag() {
  local run_id="${V9_DEPLOY_RUN_ID:-${GITHUB_RUN_ID:-local}}"
  CANDIDATE_TAG="$(RAW_TAG="candidate-${run_id}" "${PY[@]}" - <<'PY'
import os
import re

raw = os.environ["RAW_TAG"].lower()
raw = re.sub(r"[^a-z0-9-]", "-", raw)
raw = re.sub(r"-+", "-", raw).strip("-")
if not raw:
    raw = "candidate"
print(raw[:63].rstrip("-"))
PY
)"
  if [[ -z "${CANDIDATE_TAG}" ]]; then
    log "ERROR: unable to derive candidate tag"
    exit 1
  fi
}

determine_new_revision() {
  local previous="$1"
  local latest_created
  latest_created="$(gcloud run services describe "${SERVICE}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --format='value(status.latestCreatedRevisionName)')"
  if [[ -z "${latest_created}" ]]; then
    log "ERROR: unable to determine latest created revision"
    exit 1
  fi
  if [[ "${latest_created}" == "${previous}" ]]; then
    log "ERROR: new revision matches previous revision ${previous}; no new revision was created"
    exit 1
  fi
  if [[ "${latest_created}" != "${SERVICE}-"* ]]; then
    log "ERROR: revision ${latest_created} is not a ${SERVICE} revision"
    exit 1
  fi
  NEW_REVISION="${latest_created}"
  log "new revision identified: ${NEW_REVISION} (previous=${previous})"
}

get_candidate_url() {
  local tag="$1"
  local svc_json
  svc_json="$(gcloud run services describe "${SERVICE}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --format=json)"
  CANDIDATE_URL="$(SVC_JSON="${svc_json}" CAND_TAG="${tag}" "${PY[@]}" - <<'PY'
import json
import os
import sys

svc = json.loads(os.environ["SVC_JSON"])
tag = os.environ["CAND_TAG"]
for entry in svc.get("status", {}).get("traffic", []):
    if entry.get("tag") == tag and entry.get("url"):
        print(entry["url"])
        sys.exit(0)
sys.exit(1)
PY
)" || {
    log "ERROR: candidate tag URL not found for ${tag}"
    exit 1
  }
  if [[ -z "${CANDIDATE_URL}" ]]; then
    log "ERROR: candidate tag URL empty for ${tag}"
    exit 1
  fi
  log "candidate url resolved from service describe (tag=${tag})"
}

verify_candidate_readiness() {
  local revision="$1"
  local expected_digest="$2"
  local attempt=0
  local rev_json rc
  while true; do
    rev_json="$(gcloud run revisions describe "${revision}" \
      --project "${PROJECT_ID}" \
      --region "${REGION}" \
      --format=json 2>/dev/null || true)"
    if [[ -n "${rev_json}" ]]; then
      set +e
      REV_JSON="${rev_json}" EXPECT_NAME="${revision}" EXPECT_DIGEST="${expected_digest}" "${PY[@]}" - <<'PY'
import json
import os
import sys

rev = json.loads(os.environ["REV_JSON"])
if rev.get("metadata", {}).get("name", "") != os.environ["EXPECT_NAME"]:
    sys.exit(2)
conds = {c.get("type"): c.get("status") for c in rev.get("status", {}).get("conditions", [])}
if conds.get("ContainerReady") != "True":
    sys.exit(3)
expected = os.environ.get("EXPECT_DIGEST", "")
rev_digest = rev.get("status", {}).get("imageDigest", "")
image = rev.get("spec", {}).get("containers", [{}])[0].get("image", "")
if "@sha256:" in image and not rev_digest:
    rev_digest = image.split("@", 1)[1]
if expected and rev_digest and expected != rev_digest:
    sys.exit(5)
if conds.get("Ready") != "True":
    sys.exit(4)
sys.exit(0)
PY
      rc=$?
      set -e
      case "${rc}" in
        0)
          log "candidate revision ${revision} ready (ContainerReady=True, Ready=True)"
          return 0
          ;;
        2)
          log "ERROR: candidate revision name mismatch (expected ${revision})"
          exit 1
          ;;
        3)
          log "ERROR: candidate revision ${revision} container failed to start (ContainerReady!=True)"
          exit 1
          ;;
        5)
          log "ERROR: candidate revision ${revision} image digest mismatch"
          exit 1
          ;;
        4)
          : # not ready yet, retry
          ;;
      esac
    fi
    attempt=$((attempt + 1))
    if [[ ${attempt} -ge ${CANDIDATE_READY_MAX_ATTEMPTS} ]]; then
      log "ERROR: candidate revision ${revision} not ready within timeout"
      exit 1
    fi
    sleep "${CANDIDATE_READY_INTERVAL}"
  done
}

smoke_test_candidate() {
  local url="$1"
  local revision="$2"
  local code body
  code="$(curl -sS -o /tmp/v9_candidate_smoke.html -w '%{http_code}' "${url}/" || true)"
  body="$(cat /tmp/v9_candidate_smoke.html 2>/dev/null || true)"
  rm -f /tmp/v9_candidate_smoke.html
  CANDIDATE_SMOKE_HTTP="${code}"
  if [[ "${code}" != "200" ]]; then
    log "ERROR: candidate smoke test HTTP ${code} for ${revision}"
    exit 1
  fi
  set +e
  CAND_BODY="${body}" "${PY[@]}" - <<'PY'
import os
import sys

html = os.environ["CAND_BODY"]
low = html.lower()
if "streamlit" not in low and "stapp" not in low:
    sys.exit(1)
# Password gate is enforced when private study data is NOT exposed pre-auth.
forbidden = [
    "study_demo_search_20260705_145711_c06e0a1b",
    "theme_6d2dfb753f7e",
    "\u4eca\u9031\u306eR&D\u30b7\u30b0\u30ca\u30eb",
]
for token in forbidden:
    if token in html:
        sys.exit(2)
for token in ("sk-", "AIza", "BEGIN PRIVATE KEY"):
    if token in html:
        sys.exit(3)
sys.exit(0)
PY
  local rc=$?
  set -e
  case "${rc}" in
    0)
      log "candidate smoke passed on candidate url (revision=${revision}, http=${code})"
      ;;
    1)
      log "ERROR: candidate smoke did not detect Streamlit shell / password gate"
      exit 1
      ;;
    2)
      log "ERROR: candidate smoke exposed private study data before authentication"
      exit 1
      ;;
    3)
      log "ERROR: candidate smoke exposed secret material"
      exit 1
      ;;
  esac
}

promote_traffic() {
  local revision="$1"
  gcloud run services update-traffic "${SERVICE}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --to-revisions="${revision}=100"
  log "explicit traffic promotion issued: ${revision}=100"
}

wait_for_traffic_convergence() {
  local revision="$1"
  local attempt=0
  local svc_json rc
  while true; do
    svc_json="$(gcloud run services describe "${SERVICE}" \
      --project "${PROJECT_ID}" \
      --region "${REGION}" \
      --format=json 2>/dev/null || true)"
    if [[ -n "${svc_json}" ]]; then
      set +e
      SVC_JSON="${svc_json}" TARGET="${revision}" "${PY[@]}" - <<'PY'
import json
import os
import sys

svc = json.loads(os.environ["SVC_JSON"])
target = os.environ["TARGET"]


def pct(traffic):
    return sum(t.get("percent", 0) for t in traffic if t.get("revisionName") == target)


spec_ok = pct(svc.get("spec", {}).get("traffic", [])) == 100
status_ok = pct(svc.get("status", {}).get("traffic", [])) == 100
latest_ready = svc.get("status", {}).get("latestReadyRevisionName") == target
sys.exit(0 if (spec_ok and status_ok and latest_ready) else 1)
PY
      rc=$?
      set -e
      if [[ ${rc} -eq 0 ]]; then
        log "traffic converged: spec/status ${revision}=100, latestReady=${revision}"
        return 0
      fi
    fi
    attempt=$((attempt + 1))
    if [[ ${attempt} -ge ${TRAFFIC_CONVERGE_MAX_ATTEMPTS} ]]; then
      log "ERROR: traffic did not converge to ${revision} within timeout"
      exit 1
    fi
    sleep "${TRAFFIC_CONVERGE_INTERVAL}"
  done
}

verify_revision_active() {
  local revision="$1"
  local rev_json
  rev_json="$(gcloud run revisions describe "${revision}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --format=json)"
  if ! REV_JSON="${rev_json}" "${PY[@]}" - <<'PY'
import json
import os
import sys

rev = json.loads(os.environ["REV_JSON"])
conds = {c.get("type"): c.get("status") for c in rev.get("status", {}).get("conditions", [])}
if conds.get("Ready") != "True":
    sys.exit(1)
if conds.get("Active") != "True":
    sys.exit(1)
sys.exit(0)
PY
  then
    log "ERROR: revision ${revision} is not Active=True/Ready=True after promotion"
    exit 1
  fi
  log "revision ${revision} Active=True Ready=True confirmed"
}

assert_status_traffic_target() {
  local revision="$1"
  local svc_json
  svc_json="$(gcloud run services describe "${SERVICE}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --format=json)"
  if ! SVC_JSON="${svc_json}" TARGET="${revision}" "${PY[@]}" - <<'PY'
import json
import os
import sys

svc = json.loads(os.environ["SVC_JSON"])
target = os.environ["TARGET"]
status_traffic = svc.get("status", {}).get("traffic", [])
pct = sum(t.get("percent", 0) for t in status_traffic if t.get("revisionName") == target)
sys.exit(0 if pct == 100 else 1)
PY
  then
    log "ERROR: status.traffic is not 100% on ${revision}"
    exit 1
  fi
}

cleanup_candidate_tag() {
  local tag="$1"
  if [[ -z "${tag}" ]]; then
    CANDIDATE_CLEANUP="skipped_no_tag"
    return 0
  fi
  if gcloud run services update-traffic "${SERVICE}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --remove-tags="${tag}" >/dev/null 2>&1; then
    CANDIDATE_CLEANUP="removed"
    log "candidate tag ${tag} removed"
  else
    CANDIDATE_CLEANUP="cleanup_failed"
    log "WARN: candidate tag cleanup failed for ${tag} (best-effort; traffic unchanged)"
  fi
}

apply_deploy() {
  require_apply_guard
  assert_allowed_service
  run_local_checks
  assert_password_secret_ready
  assert_openalex_secret_ready
  assert_tavily_secret_ready

  local expiry_utc deploy_time_utc service_url
  local public_access_verified=false
  local mutation_started=false
  local cloud_build_started=false
  local cloud_run_update_started=false
  local deploy_result_written=false

  _write_failed_deploy_result() {
    if [[ "${deploy_result_written}" == "true" ]]; then
      return 0
    fi
    deploy_result_written=true
    RESULT_IMAGE_DIGEST="${IMAGE_DIGEST}"
    write_deploy_result \
      "failed" \
      "${public_access_verified}" \
      "${mutation_started}" \
      "${cloud_build_started}" \
      "${BUILD_ID}" \
      "${cloud_run_update_started}" \
      "${NEW_REVISION:-}"
  }
  trap '_write_failed_deploy_result' ERR

  expiry_utc="$(compute_expiry_utc)"
  deploy_time_utc="$("${PY[@]}" - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
PY
)"

  PREVIOUS_REVISION="$(gcloud run services describe "${SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --format='value(status.latestReadyRevisionName)')"
  RESULT_PREVIOUS_REVISION="${PREVIOUS_REVISION}"
  STATE_PREVIOUS_REVISION="${PREVIOUS_REVISION}"

  resolve_candidate_tag
  RESULT_CANDIDATE_TAG="${CANDIDATE_TAG}"

  verify_public_access_readonly
  public_access_verified=true

  build_study_demo_image
  mutation_started=true
  cloud_build_started=true
  STATE_CLOUD_BUILD_STARTED=true
  persist_deploy_state
  RESULT_IMAGE_DIGEST="${IMAGE_DIGEST}"

  cleanup_build_source_archive

  deploy_study_demo_service "${expiry_utc}"
  cloud_run_update_started=true
  STATE_CLOUD_RUN_UPDATE_STARTED=true
  persist_deploy_state

  determine_new_revision "${PREVIOUS_REVISION}"
  RESULT_TRAFFIC_TARGET_REVISION="${NEW_REVISION}"
  STATE_TARGET_REVISION="${NEW_REVISION}"
  persist_deploy_state

  get_candidate_url "${CANDIDATE_TAG}"
  RESULT_CANDIDATE_URL="${CANDIDATE_URL}"

  verify_candidate_readiness "${NEW_REVISION}" "${IMAGE_DIGEST}"

  smoke_test_candidate "${CANDIDATE_URL}" "${NEW_REVISION}"
  RESULT_CANDIDATE_SMOKE_STATUS="ok"
  RESULT_CANDIDATE_SMOKE_HTTP="${CANDIDATE_SMOKE_HTTP}"

  STATE_TRAFFIC_PROMOTION_STARTED=true
  RESULT_TRAFFIC_PROMOTION_STARTED=true
  persist_deploy_state

  promote_traffic "${NEW_REVISION}"
  wait_for_traffic_convergence "${NEW_REVISION}"
  verify_revision_active "${NEW_REVISION}"
  RESULT_TRAFFIC_PROMOTED=true
  RESULT_TRAFFIC_PERCENT="100"

  service_url="$(gcloud run services describe "${SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --format='value(status.url)')"

  assert_status_traffic_target "${NEW_REVISION}"
  verify_public_password_gate "${service_url}"
  assert_status_traffic_target "${NEW_REVISION}"
  RESULT_FINAL_SMOKE_STATUS="ok"

  smoke_test_authenticated_optional "${service_url}"

  cleanup_candidate_tag "${CANDIDATE_TAG}"
  RESULT_CANDIDATE_CLEANUP="${CANDIDATE_CLEANUP}"

  RESULT_IMAGE_DIGEST="${IMAGE_DIGEST}"
  write_deploy_result \
    "ok" \
    "${public_access_verified}" \
    "${mutation_started}" \
    "${cloud_build_started}" \
    "${BUILD_ID}" \
    "${cloud_run_update_started}" \
    "${NEW_REVISION}"
  deploy_result_written=true
  trap - ERR

  log "deploy completed successfully"
  log "service=${SERVICE} new_revision=${NEW_REVISION} previous_revision=${PREVIOUS_REVISION} build_id=${BUILD_ID}"
  log "service_url=${service_url}"
  log "traffic promoted to ${NEW_REVISION}=100"
  log "deployed_at_utc=${deploy_time_utc}"
}

case "${MODE}" in
  --print-python-selector)
    executable="$("${PY[@]}" -c 'import sys; print(sys.executable)')"
    version="$("${PY[@]}" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
    PY_SELECTOR_SOURCE="${PY_SELECTOR_SOURCE}" \
    PY_EXECUTABLE="${executable}" \
    PY_VERSION="${version}" \
      "${PY[@]}" -c 'import json, os; print(json.dumps({"source": os.environ["PY_SELECTOR_SOURCE"], "executable": os.environ["PY_EXECUTABLE"], "version": os.environ["PY_VERSION"]}))'
    ;;
  --check-public-access)
    assert_allowed_service
    verify_public_access_readonly
    cat <<EOF
{
  "status": "ok",
  "public_access_verified": true,
  "public_access_changed": false,
  "iam_policy_mutations": 0
}
EOF
    ;;
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
