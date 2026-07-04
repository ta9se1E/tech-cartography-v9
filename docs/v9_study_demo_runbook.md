# Tech Cartography v9 Study Demo Runbook

## Purpose

Provide a one-week, isolated Cloud Run service for internal study sessions. Participants share one demo state, authenticate with a shared password, and operate on copied production artifacts without triggering external APIs or affecting production weekly delivery.

## Isolation from production

| Resource | Production | Study demo |
|----------|------------|------------|
| Cloud Run Service | `tech-cartography-v9-signal-watch` (IAP) | `tech-cartography-v9-study-demo` (public + app password) |
| Cloud Run Job | `tech-cartography-v9-weekly-watch` | **none** |
| Scheduler | `tech-cartography-v9-weekly-watch-scheduler` | **none** |
| Bucket | `tech-cartography-v9-weekly-persist-1020686343587` | `tech-cartography-v9-study-demo-1020686343587` |
| Service Account | production / job / scheduler SAs | `tech-cartography-v9-study-demo@devops-ai-agent-hackathon-2026.iam.gserviceaccount.com` |
| Password secret | n/a | `tech-cartography-v9-study-demo-password` |

Production resources must never be modified by study demo scripts.

## Authentication

- Enabled only when `V9_STUDY_DEMO_MODE=true`
- Shared password supplied via Secret Manager env `V9_STUDY_DEMO_PASSWORD`
- Comparison uses constant-time digest check
- Session state is Streamlit session only (no persistent login)
- Logout button clears session authentication
- `V9_STUDY_DEMO_EXPIRES_AT` (UTC) blocks login after expiry (7 days from Stage B deploy)
- Secret missing → fail closed

## Shared state

- All participants see and modify the same `active/` prefix in the demo bucket
- Banner explains shared state and disabled external execution

## Disabled external operations

- BigQuery, OpenAlex, Tavily, Google Grounding
- SMTP / email send
- Cloud Run Job execute
- Cloud Scheduler admin
- External AI regeneration

## Bucket layout

| Prefix | Role |
|--------|------|
| `seed/` | Initial copied production artifacts (read-only for participants) |
| `active/` | Shared working state |
| `reset_history/` | Admin reset audit records |

## Data copy (Stage B)

Source run (read-only reference):

`cloud_weekly_job_20260704_181253`

Helper:

```bash
PYTHONPATH=.:src python scripts/prepare_v9_study_demo_seed.py --plan
V9_STUDY_DEMO_DATA_COPY_APPROVED=true PYTHONPATH=.:src python scripts/prepare_v9_study_demo_seed.py --apply
```

Copied artifacts include digest, diff, status, manifest, provider log, integrated signals, watch profile, sanitized weekly settings. Email delivery logs, recipients, locks, and secrets are excluded.

## Reset (admin terminal only)

```bash
PYTHONPATH=.:src python scripts/reset_v9_study_demo_data.py --plan
V9_STUDY_DEMO_RESET_APPROVED=true PYTHONPATH=.:src python scripts/reset_v9_study_demo_data.py --apply
```

## Password creation (Stage B)

Run locally in a normal terminal (not via chat):

```bash
cd /path/to/PatentScout_AI_v9_study_demo
conda activate 2026hack
V9_STUDY_DEMO_PASSWORD_APPROVED=true PYTHONPATH=.:src python scripts/create_v9_study_demo_password.py --apply
```

Rules: getpass twice, minimum 16 characters, no CLI args, no file output.

## Deploy (Stage B)

```bash
bash scripts/deploy_v9_study_demo.sh --plan
V9_STUDY_DEMO_DEPLOY_APPROVED=true bash scripts/deploy_v9_study_demo.sh --apply
```

- Service allowlist: `tech-cartography-v9-study-demo` only
- min instances 0, max instances 1
- No Job, no Scheduler, no SMTP secrets
- Public IAM only on study demo service

## Cleanup (after study week)

```bash
bash scripts/cleanup_v9_study_demo.sh --plan
V9_STUDY_DEMO_CLEANUP_APPROVED=true bash scripts/cleanup_v9_study_demo.sh --apply
```

Production denylist is enforced in the script.

## Stage B IAM (plan only in Stage A)

Study demo service account:

- `roles/storage.objectAdmin` on demo bucket only
- `roles/secretmanager.secretAccessor` on demo password secret only

Do **not** grant BigQuery, production bucket, SMTP, Tavily, Job, or Scheduler permissions.

## Verify production unchanged

```bash
gcloud run services describe tech-cartography-v9-signal-watch --region=us-central1 --format='value(status.latestReadyRevisionName)'
gcloud scheduler jobs describe tech-cartography-v9-weekly-watch-scheduler --location=us-central1 --format='value(state)'
```

Expected: production revision unchanged, Scheduler ENABLED, weekly enabled true.

## Rollback

If study demo deploy fails, run cleanup plan/apply for demo resources only. Do not pause production Scheduler or revert production Job settings.

## Stage A status

Stage A delivers code, tests, helpers (`--plan` only), and this runbook. No Cloud resources are created in Stage A.
