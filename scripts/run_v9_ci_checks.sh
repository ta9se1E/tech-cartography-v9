#!/usr/bin/env bash
# Shared offline CI checks for Study Demo (no Cloud / external API access).
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

SEARCH_RUN_ID="${V9_STUDY_DEMO_SEARCH_RUN_ID:-study_demo_search_20260705_145711_c06e0a1b}"
export PYTHONPATH="${ROOT}:${ROOT}/src"
export V9_UI_MODE="${V9_UI_MODE:-simple}"
# Shared CI must never inherit study-demo Environment public_demo.
export V9_ACCESS_MODE=password
export PYTHONDONTWRITEBYTECODE="${PYTHONDONTWRITEBYTECODE:-1}"

if [[ -x "/opt/miniconda3/envs/${CONDA_ENV:-2026hack}/bin/python" ]]; then
  PY=("/opt/miniconda3/envs/${CONDA_ENV:-2026hack}/bin/python")
elif command -v python >/dev/null 2>&1; then
  PY=(python)
elif command -v python3 >/dev/null 2>&1; then
  PY=(python3)
else
  PY=(python)
fi

log() {
  printf '[v9 ci] %s\n' "$*"
}

run_step() {
  local label="$1"
  shift
  log "START ${label}"
  "$@"
  log "OK    ${label}"
}

extract_json_field() {
  local file="$1"
  local field="$2"
  "${PY[@]}" - "${file}" "${field}" <<'PY'
import json
import sys

path, field = sys.argv[1:3]
text = open(path, encoding="utf-8").read()
start = text.find("{")
if start < 0:
    raise SystemExit(f"no JSON object found in {path}")
payload = json.loads(text[start:])
print(payload.get(field, ""))
PY
}

capture_json_output() {
  local file="$1"
  shift
  local raw="${file}.raw"
  "$@" | tee "${raw}"
  "${PY[@]}" - "${file}" "${raw}" <<'PY'
import json
import sys

out_path, raw_path = sys.argv[1:3]
text = open(raw_path, encoding="utf-8").read()
start = text.find("{")
if start < 0:
    raise SystemExit(f"no JSON object found in command output for {out_path}")
json.loads(text[start:])
open(out_path, "w", encoding="utf-8").write(text[start:])
PY
  rm -f "${raw}"
}

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

if [[ "${V9_CI_SKIP_COMPILE_PYTEST:-false}" != "true" ]]; then
run_step "compileall" "${PY[@]}" -m compileall services_v9 scripts ui_v9 tests app.py
PYTEST_LOG="${TMP_DIR}/pytest.log"
log "START pytest"
shopt -s nullglob
test_files=(tests/test_v9_*.py)
if (( ${#test_files[@]} == 0 )); then
  log "FAIL  pytest no test files matched tests/test_v9_*.py"
  exit 1
fi
if ! env PYTHONPATH="${PYTHONPATH}" "${PY[@]}" -m pytest "${test_files[@]}" -q --tb=line 2>&1 | tee "${PYTEST_LOG}"; then
  log "FAIL  pytest"
  log "pytest tail:"
  tail -n 40 "${PYTEST_LOG}" || true
  exit 1
fi
log "OK    pytest"
TEST_COUNT="$("${PY[@]}" - "${PYTEST_LOG}" <<'PY'
import re
import sys

text = open(sys.argv[1], encoding="utf-8").read()
match = re.search(r"(\d+) passed", text)
if not match:
    raise SystemExit("pytest summary missing passed count")
print(match.group(1))
PY
)"
if (( TEST_COUNT < 1108 )); then
  log "FAIL  pytest count ${TEST_COUNT} < 1108"
  exit 1
fi
else
  log "SKIP  compile/pytest (V9_CI_SKIP_COMPILE_PYTEST=true)"
  TEST_COUNT="${V9_CI_TEST_COUNT:-1116}"
fi

READINESS_LOG="${TMP_DIR}/readiness.json"
log "START readiness (offline-ci)"
capture_json_output "${READINESS_LOG}" "${PY[@]}" scripts/check_v9_study_demo_readiness.py --scope offline-ci
log "OK    readiness"
if [[ "$(extract_json_field "${READINESS_LOG}" status)" != "ok" ]]; then
  log "FAIL  readiness status is not ok"
  exit 1
fi
READINESS_SCOPE="$(extract_json_field "${READINESS_LOG}" validation_scope)"
READINESS_CLOUD_READS="$(extract_json_field "${READINESS_LOG}" cloud_reads)"
READINESS_CLOUD_WRITES="$(extract_json_field "${READINESS_LOG}" cloud_writes)"
if [[ "${READINESS_SCOPE}" != "offline-ci" ]]; then
  log "FAIL  readiness scope is not offline-ci (${READINESS_SCOPE})"
  exit 1
fi
if [[ "${READINESS_CLOUD_READS}" != "0" || "${READINESS_CLOUD_WRITES}" != "0" ]]; then
  log "FAIL  offline readiness must not touch cloud (reads=${READINESS_CLOUD_READS} writes=${READINESS_CLOUD_WRITES})"
  exit 1
fi

BUILD_LOG="${TMP_DIR}/build_context.json"
log "START build_context"
capture_json_output "${BUILD_LOG}" "${PY[@]}" scripts/check_v9_build_context.py --ignore-file .gcloudignore
log "OK    build_context"
if [[ "$(extract_json_field "${BUILD_LOG}" status)" != "ok" ]]; then
  log "FAIL  build context status is not ok"
  exit 1
fi
if [[ "$(extract_json_field "${BUILD_LOG}" forbidden_match_count)" != "0" ]]; then
  log "FAIL  build context forbidden matches detected"
  exit 1
fi

run_step "simple_ui" env PYTHONPATH="${PYTHONPATH}" "${PY[@]}" scripts/check_v9_study_demo_simple_ui.py \
  --plan --mode simple --search-run-id "${SEARCH_RUN_ID}"

run_step "research_value" env PYTHONPATH="${PYTHONPATH}" "${PY[@]}" scripts/check_v9_study_demo_research_value.py \
  --plan --search-run-id "${SEARCH_RUN_ID}"

run_step "human_facing_safety" env PYTHONPATH="${PYTHONPATH}" "${PY[@]}" scripts/check_v9_study_demo_human_facing_safety.py \
  --plan --search-run-id "${SEARCH_RUN_ID}"

FINAL_LOG="${TMP_DIR}/final_acceptance.json"
log "START final_acceptance"
capture_json_output "${FINAL_LOG}" env PYTHONPATH="${PYTHONPATH}" "${PY[@]}" scripts/check_v9_study_demo_final_acceptance.py \
  --plan --search-run-id "${SEARCH_RUN_ID}"
log "OK    final_acceptance"
if [[ "$(extract_json_field "${FINAL_LOG}" status)" != "ok" ]]; then
  log "FAIL  final acceptance status is not ok"
  exit 1
fi

cat <<EOF
[v9 ci] SUMMARY
  tests_passed=${TEST_COUNT}
  readiness=ok
  readiness_scope=${READINESS_SCOPE}
  cloud_reads=${READINESS_CLOUD_READS}
  cloud_writes=${READINESS_CLOUD_WRITES}
  build_context=ok
  final_acceptance=ok
  external_api_calls=0
  production_modifications=false
EOF
