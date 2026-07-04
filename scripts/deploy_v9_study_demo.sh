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
PASSWORD_SECRET_VERSION="${PASSWORD_SECRET_VERSION:-}"
V9_PERSIST_ROOT="${V9_PERSIST_ROOT:-/mnt/v9_study_demo}"
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
  "password_secret": "${PASSWORD_SECRET}",
  "min_instances": 0,
  "max_instances": 1,
  "scheduler": "none",
  "cloud_run_job": "none",
  "public_service": "${SERVICE} only",
  "production_resources_modified": false,
  "env": {
    "V9_STUDY_DEMO_MODE": "true",
    "V9_STUDY_DEMO_BUCKET": "${BUCKET}",
    "V9_STUDY_DEMO_DISABLE_EXTERNAL_EXECUTION": "true",
    "V9_STUDY_DEMO_SHARED_STATE": "true",
    "V9_ENABLE_EMAIL_SEND": "false",
    "DISABLE_EMAIL_SEND": "true",
    "EMAIL_SEND_MODE": "preview",
    "V9_CLOUD_ENABLE_PATENT": "false",
    "V9_CLOUD_ENABLE_PAPER": "false",
    "V9_CLOUD_ENABLE_WEB_COMPANY": "false",
    "V9_CLOUD_GOOGLE_GROUNDING": "false"
  },
  "apply_guard": "V9_STUDY_DEMO_DEPLOY_APPROVED=true",
  "notes": [
    "Stage A does not deploy",
    "V9_STUDY_DEMO_EXPIRES_AT is set at deploy time to UTC+7days",
    "seed data is copied separately via prepare_v9_study_demo_seed.py"
  ]
}
EOF
}

apply_deploy() {
  require_apply_guard
  assert_allowed_service
  log "ERROR: Stage A blocks --apply deploy. Run Stage B after password and seed preparation."
  exit 1
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
