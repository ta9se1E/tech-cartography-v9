#!/usr/bin/env bash
# Safe v9 Cloud Build submit helper with explicit ignore-file and source cleanup.
set -euo pipefail

MODE="${1:---plan}"
PROJECT_ID="${PROJECT_ID:-devops-ai-agent-hackathon-2026}"
REGION="${REGION:-us-central1}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if command -v conda >/dev/null 2>&1; then
  PY=(conda run -n "${CONDA_ENV:-2026hack}" python)
else
  PY=(python3)
fi

export PYTHONPATH="${ROOT}:${ROOT}/src"

NEW_COMMIT="$(git rev-parse --short HEAD)"
IMAGE_URI_DEFAULT="${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/tech-cartography-v9-signal-watch:${NEW_COMMIT}"
IMAGE_URI="${IMAGE_URI:-${IMAGE_URI_DEFAULT}}"
BUILD_ID=""
SOURCE_BUCKET=""
SOURCE_OBJECT=""
SOURCE_GENERATION=""
BUILD_STATUS=""
CLEANUP_ATTEMPTED="false"
CLEANUP_RESULT="not_started"

log() {
  printf '%s\n' "$*"
}

usage() {
  cat <<'EOF'
Usage:
  scripts/submit_v9_cloud_build_safe.sh --plan
  V9_CLOUD_CHANGE_APPROVED=true scripts/submit_v9_cloud_build_safe.sh --apply

Default mode is --plan. Applying requires V9_CLOUD_CHANGE_APPROVED=true.
EOF
}

require_apply_guard() {
  if [[ "${V9_CLOUD_CHANGE_APPROVED:-false}" != "true" ]]; then
    log "ERROR: --apply requires V9_CLOUD_CHANGE_APPROVED=true"
    exit 1
  fi
}

check_build_context() {
  "${PY[@]}" scripts/check_v9_build_context.py --ignore-file .gcloudignore
}

describe_build_json() {
  gcloud builds describe "${BUILD_ID}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --format=json
}

load_source_target() {
  if [[ -z "${BUILD_ID}" ]]; then
    return 0
  fi
  local build_json
  build_json="$(describe_build_json)"
  local export_lines
  export_lines="$("${PY[@]}" - <<'PY' <<<"${build_json}"
import json
import shlex
import sys
from scripts.v9_build_security import build_source_cleanup_target

payload = json.load(sys.stdin)
target = build_source_cleanup_target(payload)
print(f"SOURCE_BUCKET={shlex.quote(str(target.get('bucket', '') or ''))}")
print(f"SOURCE_OBJECT={shlex.quote(str(target.get('object', '') or ''))}")
print(f"SOURCE_GENERATION={shlex.quote(str(target.get('generation', '') or ''))}")
print(f"SOURCE_TARGET_STATUS={shlex.quote(str(target.get('status', '') or ''))}")
print(f"SOURCE_TARGET_REASON={shlex.quote(str(target.get('reason', '') or ''))}")
PY
)"
  eval "${export_lines}"
}

cleanup_source_archive() {
  if [[ "${CLEANUP_ATTEMPTED}" == "true" ]]; then
    return 0
  fi
  CLEANUP_ATTEMPTED="true"
  if [[ -z "${BUILD_ID}" ]]; then
    CLEANUP_RESULT="skipped_no_build"
    return 0
  fi
  load_source_target
  if [[ "${SOURCE_TARGET_STATUS:-}" != "ok" || -z "${SOURCE_BUCKET}" || -z "${SOURCE_OBJECT}" ]]; then
    CLEANUP_RESULT="skipped_${SOURCE_TARGET_REASON:-invalid_target}"
    return 0
  fi
  if gcloud storage rm "gs://${SOURCE_BUCKET}/${SOURCE_OBJECT}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    if gcloud storage ls "gs://${SOURCE_BUCKET}/${SOURCE_OBJECT}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
      CLEANUP_RESULT="delete_not_verified"
    else
      CLEANUP_RESULT="deleted"
    fi
    return 0
  fi
  CLEANUP_RESULT="delete_failed"
}

trap cleanup_source_archive EXIT

wait_for_build() {
  while true; do
    BUILD_STATUS="$(gcloud builds describe "${BUILD_ID}" --project "${PROJECT_ID}" --region "${REGION}" --format='value(status)')"
    case "${BUILD_STATUS}" in
      QUEUED|WORKING|PENDING)
        sleep 5
        ;;
      *)
        return 0
        ;;
    esac
  done
}

print_plan() {
  cat <<EOF
Safe v9 Cloud Build plan only. No Cloud change has been executed.

- project: ${PROJECT_ID}
- region: ${REGION}
- image: ${IMAGE_URI}
- ignore file: .gcloudignore
- preflight: python scripts/check_v9_build_context.py --ignore-file .gcloudignore
- build: gcloud builds submit . --project "${PROJECT_ID}" --region "${REGION}" --ignore-file=.gcloudignore --config cloudbuild.v9.yaml --substitutions "_IMAGE_URI=${IMAGE_URI}" --async
- cleanup: exact source.storageSource bucket/object only
EOF
}

apply_build() {
  require_apply_guard
  check_build_context
  BUILD_ID="$(gcloud builds submit . \
    --async \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --ignore-file=.gcloudignore \
    --config cloudbuild.v9.yaml \
    --substitutions "_IMAGE_URI=${IMAGE_URI}" \
    --format='value(metadata.build.id)')"
  if [[ -z "${BUILD_ID}" ]]; then
    log "ERROR: failed to obtain Cloud Build ID"
    exit 1
  fi
  wait_for_build
  local build_json
  build_json="$(describe_build_json)"
  "${PY[@]}" - <<'PY' <<<"${build_json}"
import json
import sys
payload = json.load(sys.stdin)
result_images = []
for item in payload.get("results", {}).get("images", []) or []:
  if isinstance(item, dict):
    result_images.append({
      "name": str(item.get("name", "") or ""),
      "digest": str(item.get("digest", "") or ""),
    })
print(json.dumps({
  "build_id": str(payload.get("id", "") or ""),
  "status": str(payload.get("status", "") or ""),
  "result_images": result_images,
}, ensure_ascii=False, indent=2))
PY
  if [[ "${BUILD_STATUS}" != "SUCCESS" ]]; then
    exit 1
  fi
}

main() {
  case "${MODE}" in
    --plan)
      print_plan
      ;;
    --apply)
      apply_build
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
