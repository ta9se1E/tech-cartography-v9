#!/usr/bin/env bash
# Plan/apply cleanup helper for the isolated Tech Cartography v9 study demo resources.
set -euo pipefail

MODE="${1:---plan}"
PROJECT_ID="${PROJECT_ID:-devops-ai-agent-hackathon-2026}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-tech-cartography-v9-study-demo}"
BUCKET="${BUCKET:-tech-cartography-v9-study-demo-1020686343587}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-tech-cartography-v9-study-demo@devops-ai-agent-hackathon-2026.iam.gserviceaccount.com}"
PASSWORD_SECRET="${PASSWORD_SECRET:-tech-cartography-v9-study-demo-password}"

PRODUCTION_DENY=(
  "tech-cartography-v9-signal-watch"
  "tech-cartography-v9-weekly-watch"
  "tech-cartography-v9-weekly-watch-scheduler"
  "tech-cartography-v9-weekly-persist-1020686343587"
  "tech-cartography-smtp-password"
  "tech-cartography-tavily-api-key"
)

log() {
  printf '%s\n' "$*"
}

assert_not_production_resource() {
  local target="$1"
  local denied
  for denied in "${PRODUCTION_DENY[@]}"; do
    if [[ "${target}" == "${denied}" ]]; then
      log "ERROR: production resource is denylisted: ${target}"
      exit 1
    fi
  done
}

require_apply_guard() {
  if [[ "${V9_STUDY_DEMO_CLEANUP_APPROVED:-false}" != "true" ]]; then
    log "ERROR: --apply requires V9_STUDY_DEMO_CLEANUP_APPROVED=true"
    exit 1
  fi
}

print_plan() {
  assert_not_production_resource "${SERVICE}"
  assert_not_production_resource "${BUCKET}"
  assert_not_production_resource "${PASSWORD_SECRET}"
  cat <<EOF
{
  "status": "plan",
  "delete_candidates": [
    "Cloud Run service ${SERVICE}",
    "GCS bucket objects under ${BUCKET}",
    "Secret ${PASSWORD_SECRET} versions (disable first)",
    "Service account ${SERVICE_ACCOUNT}",
    "Study demo container images"
  ],
  "production_denylist": $(printf '%s\n' "${PRODUCTION_DENY[@]}" | python3 -c 'import json,sys; print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))'),
  "apply_guard": "V9_STUDY_DEMO_CLEANUP_APPROVED=true",
  "notes": [
    "Stage A does not execute cleanup",
    "no wildcard delete",
    "secret destroy requires separate approval"
  ]
}
EOF
}

apply_cleanup() {
  require_apply_guard
  assert_not_production_resource "${SERVICE}"
  log "ERROR: Stage A blocks --apply cleanup."
  exit 1
}

case "${MODE}" in
  --plan)
    print_plan
    ;;
  --apply)
    apply_cleanup
    ;;
  *)
    log "Usage: scripts/cleanup_v9_study_demo.sh --plan|--apply"
    exit 1
    ;;
esac
