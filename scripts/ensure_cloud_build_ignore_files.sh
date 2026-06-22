#!/usr/bin/env bash
# Restore .gcloudignore / .dockerignore in Cloud Build /workspace (Phase 25P.2).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

cp "${ROOT}/config/cloudrun.gcloudignore" "${ROOT}/.gcloudignore"
cp "${ROOT}/config/cloudrun.dockerignore" "${ROOT}/.dockerignore"
