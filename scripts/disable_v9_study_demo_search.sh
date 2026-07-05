#!/usr/bin/env bash
# Plan/apply helper to disable study demo three-source search.
set -euo pipefail

MODE="${1:---plan}"
PROJECT_ID="${PROJECT_ID:-devops-ai-agent-hackathon-2026}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-tech-cartography-v9-study-demo}"
ROLLBACK_REVISION="${ROLLBACK_REVISION:-tech-cartography-v9-study-demo-00001-b48}"
ALLOWED_SERVICES=("tech-cartography-v9-study-demo")

require_apply_guard() {
  if [[ "${V9_STUDY_DEMO_SEARCH_DISABLE_APPROVED:-false}" != "true" ]]; then
    echo "ERROR: --apply requires V9_STUDY_DEMO_SEARCH_DISABLE_APPROVED=true" >&2
    exit 1
  fi
}

assert_allowed_service() {
  local ok=0
  for name in "${ALLOWED_SERVICES[@]}"; do
    if [[ "${SERVICE}" == "${name}" ]]; then ok=1; fi
  done
  if [[ "${ok}" -ne 1 ]]; then
    echo "ERROR: SERVICE not allowlisted" >&2
    exit 1
  fi
}

print_plan() {
  cat <<EOF
{
  "status": "plan",
  "service": "${SERVICE}",
  "rollback_revision": "${ROLLBACK_REVISION}",
  "actions": [
    "set V9_STUDY_DEMO_SEARCH_ENABLED=false",
    "set provider search flags false",
    "deploy read-only revision ${ROLLBACK_REVISION}",
    "remove BigQuery jobUser from demo SA",
    "remove OpenAlex/Tavily secret refs from service",
    "preserve search history artifacts",
    "do not destroy secret versions",
    "do not modify production resources"
  ],
  "apply_guard": "V9_STUDY_DEMO_SEARCH_DISABLE_APPROVED=true"
}
EOF
}

apply_disable() {
  require_apply_guard
  assert_allowed_service
  echo "ERROR: Stage C1 blocks --apply. Run in Stage C2 after search was enabled." >&2
  exit 1
}

case "${MODE}" in
  --plan) print_plan ;;
  --apply) apply_disable ;;
  *) echo "Usage: scripts/disable_v9_study_demo_search.sh --plan|--apply" >&2; exit 1 ;;
esac
