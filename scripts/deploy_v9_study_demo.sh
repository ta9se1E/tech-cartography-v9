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

write_deploy_state() {
  local mutation_started="$1"
  local state_file="${DEPLOY_STATE_FILE}"
  local tmp_file="${state_file}.tmp"
  mkdir -p "$(dirname "${state_file}")"
  if [[ "${mutation_started}" == "true" ]]; then
    printf '{"mutation_started": true}\n' > "${tmp_file}"
  else
    printf '{"mutation_started": false}\n' > "${tmp_file}"
  fi
  mv "${tmp_file}" "${state_file}"
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
  DEPLOY_RESULT_FILE="${result_file}" \
  DEPLOY_RESULT_TMP="${tmp_file}" \
    "${PY[@]}" - <<'PY'
import json
import os
import pathlib

payload = {
    "status": os.environ["DEPLOY_RESULT_STATUS"],
    "public_access_verified": os.environ["DEPLOY_RESULT_PUBLIC_ACCESS_VERIFIED"] == "true",
    "public_access_changed": False,
    "iam_policy_mutations": 0,
    "mutation_started": os.environ["DEPLOY_RESULT_MUTATION_STARTED"] == "true",
    "cloud_build_started": os.environ["DEPLOY_RESULT_CLOUD_BUILD_STARTED"] == "true",
    "cloud_build_id": os.environ["DEPLOY_RESULT_CLOUD_BUILD_ID"],
    "cloud_run_update_started": os.environ["DEPLOY_RESULT_CLOUD_RUN_UPDATE_STARTED"] == "true",
    "new_revision": os.environ["DEPLOY_RESULT_NEW_REVISION"],
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
  write_deploy_state true
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

apply_deploy() {
  require_apply_guard
  assert_allowed_service
  run_local_checks
  assert_password_secret_ready
  assert_openalex_secret_ready
  assert_tavily_secret_ready

  local expiry_utc expiry_jst deploy_time_utc deploy_time_jst service_url revision
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
    write_deploy_result \
      "failed" \
      "${public_access_verified}" \
      "${mutation_started}" \
      "${cloud_build_started}" \
      "${BUILD_ID}" \
      "${cloud_run_update_started}" \
      "${revision:-}"
  }
  trap '_write_failed_deploy_result' ERR

  expiry_utc="$(compute_expiry_utc)"
  expiry_jst="$(compute_expiry_jst "${expiry_utc}")"
  deploy_time_utc="$("${PY[@]}" - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
PY
)"
  deploy_time_jst="$(compute_expiry_jst "${deploy_time_utc}")"

  verify_public_access_readonly
  public_access_verified=true
  build_study_demo_image
  mutation_started=true
  cloud_build_started=true
  cleanup_build_source_archive
  deploy_study_demo_service "${expiry_utc}"
  cloud_run_update_started=true

  service_url="$(gcloud run services describe "${SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --format='value(status.url)')"
  revision="$(gcloud run services describe "${SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --format='value(status.latestReadyRevisionName)')"
  verify_public_password_gate "${service_url}"
  smoke_test_authenticated_optional "${service_url}"

  write_deploy_result \
    "ok" \
    "${public_access_verified}" \
    "${mutation_started}" \
    "${cloud_build_started}" \
    "${BUILD_ID}" \
    "${cloud_run_update_started}" \
    "${revision}"
  deploy_result_written=true
  trap - ERR

  log "deploy completed successfully"
  log "service=${SERVICE} revision=${revision} build_id=${BUILD_ID}"
  log "service_url=${service_url}"
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
