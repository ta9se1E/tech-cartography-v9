# GitHub Actions CI/CD for Study Demo

This document describes the approved CI and keyless Continuous Delivery foundation for the isolated Study Demo service.

## Architecture

```mermaid
flowchart LR
  subgraph CI
    PushPR[Push / PR / workflow_dispatch] --> CheckoutCI[Checkout]
    CheckoutCI --> PySetup[Python 3.11]
    PySetup --> SharedChecks[run_v9_ci_checks.sh]
  end

  subgraph CD
    ManualDeploy[workflow_dispatch Deploy] --> Preflight[Preflight tag/service guard]
    Preflight --> EnvApproval[GitHub Environment study-demo approval]
    EnvApproval --> CheckoutTag[Checkout validated tag]
    CheckoutTag --> SharedChecks2[run_v9_ci_checks.sh]
    SharedChecks2 --> WIF[Workload Identity Federation]
    WIF --> DeployPlan[deploy_v9_study_demo.sh --plan]
    DeployPlan --> DeployApply[deploy_v9_study_demo.sh --apply]
    DeployApply --> PostChecks[Post-deploy + smoke]
    PostChecks -->|failure after apply| AutoRollback[update-traffic previous revision]
    DeployPlan -->|failure before apply| SkipRollback[rollback skipped]
  end

  subgraph Rollback
    ManualRollback[workflow_dispatch Rollback] --> EnvApproval2[Environment approval]
    EnvApproval2 --> WIF2[WIF auth]
    WIF2 --> TrafficSwitch[update-traffic target revision]
    TrafficSwitch --> Smoke[Rollback smoke test]
  end
```

## CI

Workflow: `.github/workflows/ci.yml`

Triggers:

- `push` to `v9-study-demo`
- `pull_request` to `v9-study-demo`
- `workflow_dispatch`

Checks (offline only):

- compileall
- pytest (`tests/test_v9_*.py`, minimum 1108 passed)
- readiness
- build context safety
- simple UI / research value / human-facing safety / final acceptance plan checks

No gcloud auth, no WIF, no secrets, no Cloud writes, no external APIs.

## Approved Continuous Delivery

Workflow: `.github/workflows/deploy-study-demo.yml`

Trigger: **`workflow_dispatch` only**

Inputs:

- `release_tag` (default: `v9-study-demo-final-acceptance-live-validated`)
- `confirm_service` (must exactly match `tech-cartography-v9-study-demo`)

Jobs:

1. **preflight** — tag pattern, service guard, required scripts at tag
2. **deploy** — GitHub Environment `study-demo` approval, checkout validated tag, shared CI checks, WIF auth, deploy plan/apply, post-deploy validation, smoke test, automatic rollback on failure **after apply starts**

Important:

- Push alone never deploys to Cloud Run
- Application source deployed is always the validated tag commit, not the workflow branch tip
- Browser acceptance remains a human step after deploy
- GitHub-hosted runners use setup-python; deploy script selects conda only when the env exists
- Rollback runs only after `Deploy apply` starts Cloud Build (`mutation_started=true`); pre-apply failures skip traffic rollback
- Approved deploy preserves existing Cloud Run IAM; public access is verified read-only before build

## Manual rollback

Workflow: `.github/workflows/rollback-study-demo.yml`

Trigger: **`workflow_dispatch` only`

Requires Environment approval, WIF auth, revision validation, traffic switch, smoke test.

## Workload Identity Federation

Setup script: `scripts/setup_v9_github_cicd.sh`

- No Service Account key JSON
- Dedicated deployer SA: `tech-cartography-v9-gh-deploy@devops-ai-agent-hackathon-2026.iam.gserviceaccount.com`
- Runtime SA remains: `tech-cartography-v9-study-demo@...`
- Attribute condition: exact repository + `refs/heads/v9-study-demo`

Deployer SA least-privilege plan:

| Scope | Role |
|-------|------|
| project | `roles/run.sourceDeveloper` |
| project | `roles/serviceusage.serviceUsageConsumer` |
| runtime SA | `roles/iam.serviceAccountUser` |
| deployer SA | `roles/iam.workloadIdentityUser` for WIF principal |

Note: `roles/run.sourceDeveloper` may not include `run.services.updateTraffic`. Verify during setup; add `roles/run.developer` only if rollback traffic updates fail.

## Production isolation

Hard-coded guards reject:

- `tech-cartography-v9-signal-watch`
- any non-Study-Demo service name
- non-validated tag patterns

Deploy and rollback workflows never target production resources.

## GitHub setup (C5B-6B)

User actions (not executed in C5B-6A):

1. Configure `origin` remote and confirm repository visibility
2. Create GitHub Environment `study-demo` with required reviewer
3. Restrict deployment branch to `v9-study-demo`
4. Set Environment Variables (no secrets required):
   - `GCP_PROJECT_ID`
   - `GCP_PROJECT_NUMBER`
   - `GCP_REGION`
   - `CLOUD_RUN_SERVICE`
   - `RUNTIME_SERVICE_ACCOUNT`
   - `WIF_PROVIDER`
   - `DEPLOYER_SERVICE_ACCOUNT` (GitHub rejects variable names starting with `GITHUB_`)
   - `VALIDATED_RELEASE_TAG`
   - `V9_ACCESS_MODE` (`public_demo` for judge-facing Study Demo)
5. Run `bash scripts/setup_v9_github_cicd.sh --apply` after plan review

## Browser acceptance

Automated deploy verifies technical safety (revision, smoke, fixture checks). Final browser acceptance for demo recording remains manual.

### Public demo (`V9_ACCESS_MODE=public_demo`)

1. Open the Study Demo URL — no password screen
2. Simple Mode starts directly; Advanced Mode is not exposed
3. Confirm **Public Demo — read-only** badge at the top
4. Confirm seeded demo notice and legal caveat (no legal/FTO/infringement advice)
5. Confirm theme **PAN系炭素繊維用サイジング剤の組成・付与・乾燥条件**
6. Confirm Patent/Paper/Web = 5/5/5 (integrated 15)
7. Confirm Top3 research value cards
8. Browse Weekly/Digest tabs read-only
9. Attempt write operations — they must not persist after refresh
10. Confirm no external API calls during browsing
11. Refresh and confirm shared demo data is unchanged
12. Confirm secret/internal tokens are not displayed

## Video Scene 7 wording

Use:

> CIと、承認付きのContinuous Deliveryを実装しました。pushだけではStudy Demoへ自動デプロイせず、validated tag・GitHub Environment承認・Workload Identity Federationによるキーなし認証のあと、preflight/post-deploy/smoke/失敗時rollbackまでを自動化しています。

Do not say:

- 無人のContinuous Deployment
- pushで本番へ自動反映
- production自動deploy
