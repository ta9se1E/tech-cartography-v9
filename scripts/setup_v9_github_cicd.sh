#!/usr/bin/env bash
# Plan/apply helper for GitHub Actions WIF + IAM for Study Demo CD.
set -euo pipefail

MODE="${1:---plan}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

PROJECT_ID="${PROJECT_ID:-devops-ai-agent-hackathon-2026}"
REGION="${REGION:-us-central1}"
STUDY_SERVICE="${STUDY_SERVICE:-tech-cartography-v9-study-demo}"
PRODUCTION_SERVICE="${PRODUCTION_SERVICE:-tech-cartography-v9-signal-watch}"
RUNTIME_SA="${RUNTIME_SA:-tech-cartography-v9-study-demo@${PROJECT_ID}.iam.gserviceaccount.com}"
DEPLOYER_SA_NAME="${DEPLOYER_SA_NAME:-tech-cartography-v9-github-deployer}"
DEPLOYER_SA="${DEPLOYER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
WIF_POOL="${WIF_POOL:-github-actions}"
WIF_PROVIDER="${WIF_PROVIDER:-tech-cartography-v9-study-demo}"
GITHUB_BRANCH="${GITHUB_BRANCH:-v9-study-demo}"
VALIDATED_RELEASE_TAG="${VALIDATED_RELEASE_TAG:-v9-study-demo-final-acceptance-live-validated}"

log() {
  printf '%s\n' "$*"
}

usage() {
  cat <<'EOF'
Usage:
  scripts/setup_v9_github_cicd.sh --plan
  scripts/setup_v9_github_cicd.sh --apply

Stage C5B-6A defaults to --plan only. --apply creates WIF/IAM and prints GitHub setup commands.
EOF
}

resolve_github_repository() {
  if [[ -n "${GITHUB_REPOSITORY:-}" ]]; then
    printf '%s\n' "${GITHUB_REPOSITORY}"
    return 0
  fi
  if git remote get-url origin >/dev/null 2>&1; then
    git remote get-url origin | sed -E 's#^(git@github.com:|https://github.com/)##; s#\.git$##'
    return 0
  fi
  return 1
}

resolve_project_number() {
  if [[ -n "${GCP_PROJECT_NUMBER:-}" ]]; then
    printf '%s\n' "${GCP_PROJECT_NUMBER}"
    return 0
  fi
  if command -v gcloud >/dev/null 2>&1; then
    gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)'
    return 0
  fi
  printf '%s\n' "UNRESOLVED"
}

resolve_repo_visibility() {
  if command -v gh >/dev/null 2>&1 && resolve_github_repository >/dev/null 2>&1; then
    local repo
    repo="$(resolve_github_repository)"
    gh repo view "${repo}" --json visibility --jq .visibility 2>/dev/null || true
    return 0
  fi
  printf '%s\n' "UNVERIFIED"
}

require_apply_guard() {
  if [[ "${V9_GITHUB_CICD_SETUP_APPROVED:-false}" != "true" ]]; then
    log "ERROR: --apply requires V9_GITHUB_CICD_SETUP_APPROVED=true"
    exit 1
  fi
}

print_plan() {
  local github_repo="${1:-UNRESOLVED}"
  local project_number="${2:-UNRESOLVED}"
  local visibility="${3:-UNVERIFIED}"
  local wif_provider_resource=""
  if [[ "${project_number}" != "UNRESOLVED" ]]; then
    wif_provider_resource="projects/${project_number}/locations/global/workloadIdentityPools/${WIF_POOL}/providers/${WIF_PROVIDER}"
  fi

  cat <<EOF
{
  "status": "plan",
  "project_id": "${PROJECT_ID}",
  "project_number": "${project_number}",
  "region": "${REGION}",
  "study_service": "${STUDY_SERVICE}",
  "production_service": "${PRODUCTION_SERVICE}",
  "runtime_service_account": "${RUNTIME_SA}",
  "deployer_service_account": "${DEPLOYER_SA}",
  "wif_pool": "${WIF_POOL}",
  "wif_provider": "${WIF_PROVIDER}",
  "wif_provider_resource": "${wif_provider_resource}",
  "github_repository": "${github_repo}",
  "github_branch": "${GITHUB_BRANCH}",
  "repository_visibility": "${visibility}",
  "validated_release_tag": "${VALIDATED_RELEASE_TAG}",
  "service_account_key_json": "forbidden",
  "github_environment": "study-demo",
  "github_environment_reviewers": "repository owner (required reviewer; prevent_self_review=false for solo owner)",
  "github_environment_branch": "${GITHUB_BRANCH}",
  "github_variables": [
    "GCP_PROJECT_ID",
    "GCP_PROJECT_NUMBER",
    "GCP_REGION",
    "CLOUD_RUN_SERVICE=${STUDY_SERVICE}",
    "RUNTIME_SERVICE_ACCOUNT=${RUNTIME_SA}",
    "WIF_PROVIDER",
    "GITHUB_DEPLOYER_SERVICE_ACCOUNT=${DEPLOYER_SA}",
    "VALIDATED_RELEASE_TAG=${VALIDATED_RELEASE_TAG}"
  ],
  "github_secrets_required": false,
  "deployer_roles_project": [
    "roles/run.sourceDeveloper",
    "roles/serviceusage.serviceUsageConsumer"
  ],
  "deployer_roles_runtime_sa": [
    "roles/iam.serviceAccountUser"
  ],
  "deployer_roles_additional_if_needed": [
    "roles/run.developer"
  ],
  "rollback_permission_note": "roles/run.sourceDeveloper covers source deploy but may not include run.services.updateTraffic. Plan to verify during --apply; add roles/run.developer only if traffic rollback fails.",
  "wif_attribute_mapping": {
    "google.subject": "assertion.sub",
    "attribute.repository": "assertion.repository",
    "attribute.ref": "assertion.ref",
    "attribute.workflow": "assertion.workflow"
  },
  "wif_attribute_condition": "assertion.repository=='${github_repo}' && assertion.ref=='refs/heads/${GITHUB_BRANCH}'",
  "wif_principal_binding": "principalSet://iam.googleapis.com/projects/${project_number}/locations/global/workloadIdentityPools/${WIF_POOL}/providers/${WIF_PROVIDER}/attribute.repository/${github_repo}",
  "production_isolation": {
    "allowed_service": "${STUDY_SERVICE}",
    "denied_service": "${PRODUCTION_SERVICE}",
    "workflow_guard": "confirm_service exact match + validated tag checkout"
  },
  "cloud_changes_in_plan": false,
  "github_changes_in_plan": false,
  "blockers": $(if [[ "${github_repo}" == "UNRESOLVED" ]]; then printf '["github_repository_unresolved"]'; else printf '[]'; fi)
}
EOF

  {
    log ""
    log "GitHub Environment plan (not executed in --plan):"
    log "  gh api --method PUT repos/${github_repo}/environments/study-demo"
    log "  gh variable set GCP_PROJECT_ID --env study-demo --body ${PROJECT_ID}"
    log "  gh variable set GCP_PROJECT_NUMBER --env study-demo --body ${project_number}"
    log "  gh variable set GCP_REGION --env study-demo --body ${REGION}"
    log "  gh variable set CLOUD_RUN_SERVICE --env study-demo --body ${STUDY_SERVICE}"
    log "  gh variable set RUNTIME_SERVICE_ACCOUNT --env study-demo --body ${RUNTIME_SA}"
    log "  gh variable set GITHUB_DEPLOYER_SERVICE_ACCOUNT --env study-demo --body ${DEPLOYER_SA}"
    log "  gh variable set WIF_PROVIDER --env study-demo --body ${wif_provider_resource}"
    log "  gh variable set VALIDATED_RELEASE_TAG --env study-demo --body ${VALIDATED_RELEASE_TAG}"

    if [[ "${visibility}" == "UNVERIFIED" ]]; then
      log ""
      log "WARNING: repository visibility is unverified (no origin remote and gh unavailable)."
      log "WARNING: confirm repository is public or Environment protection rules are valid before C5B-6B."
    elif [[ "${visibility}" != "PUBLIC" ]]; then
      log ""
      log "WARNING: repository visibility=${visibility}. Do not assume required reviewer behavior; confirm manually."
    fi

    if [[ "${github_repo}" == "UNRESOLVED" ]]; then
      log ""
      log "BLOCKER: set git remote origin or export GITHUB_REPOSITORY before --apply."
    fi
  } >&2
}

apply_setup() {
  local github_repo="$1"
  local project_number="$2"
  log "Creating workload identity pool ${WIF_POOL} (if missing)..."
  gcloud iam workload-identity-pools create "${WIF_POOL}" \
    --project="${PROJECT_ID}" \
    --location=global \
    --display-name="GitHub Actions" || true

  log "Creating workload identity provider ${WIF_PROVIDER}..."
  gcloud iam workload-identity-pools providers create-oidc "${WIF_PROVIDER}" \
    --project="${PROJECT_ID}" \
    --location=global \
    --workload-identity-pool="${WIF_POOL}" \
    --display-name="Study Demo GitHub Actions" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref,attribute.workflow=assertion.workflow" \
    --attribute-condition="assertion.repository=='${github_repo}' && assertion.ref=='refs/heads/${GITHUB_BRANCH}'" || true

  log "Creating deployer service account ${DEPLOYER_SA}..."
  gcloud iam service-accounts create "${DEPLOYER_SA_NAME}" \
    --project="${PROJECT_ID}" \
    --display-name="Tech Cartography v9 Study Demo GitHub Deployer" || true

  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${DEPLOYER_SA}" \
    --role="roles/run.sourceDeveloper" >/dev/null
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${DEPLOYER_SA}" \
    --role="roles/serviceusage.serviceUsageConsumer" >/dev/null
  gcloud iam service-accounts add-iam-policy-binding "${RUNTIME_SA}" \
    --project="${PROJECT_ID}" \
    --member="serviceAccount:${DEPLOYER_SA}" \
    --role="roles/iam.serviceAccountUser" >/dev/null

  local principal="principalSet://iam.googleapis.com/projects/${project_number}/locations/global/workloadIdentityPools/${WIF_POOL}/providers/${WIF_PROVIDER}/attribute.repository/${github_repo}"
  gcloud iam service-accounts add-iam-policy-binding "${DEPLOYER_SA}" \
    --project="${PROJECT_ID}" \
    --role="roles/iam.workloadIdentityUser" \
    --member="${principal}" >/dev/null

  log "Apply complete. Configure GitHub Environment variables manually or via gh CLI."
}

main() {
  case "${MODE}" in
    --plan)
      local github_repo="UNRESOLVED"
      local visibility="UNVERIFIED"
      if github_repo="$(resolve_github_repository)"; then
        :
      else
        github_repo="UNRESOLVED"
      fi
      visibility="$(resolve_repo_visibility)"
      print_plan "${github_repo}" "$(resolve_project_number)" "${visibility}"
      ;;
    --apply)
      require_apply_guard
      local github_repo
      github_repo="$(resolve_github_repository)"
      print_plan "${github_repo}" "$(resolve_project_number)" "$(resolve_repo_visibility)"
      apply_setup "${github_repo}" "$(resolve_project_number)"
      ;;
    -h|--help|help)
      usage
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
