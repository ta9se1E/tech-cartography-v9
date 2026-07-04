# Tech Cartography v9 Production Go-Live Record

## Summary

| Item | Value |
|------|-------|
| Go-live date (JST) | 2026-07-05 |
| Branch | `v9-signal-watch` |
| Start HEAD | `e95498d` |
| Rollback checkpoint | `backup/v9-before-production-go-live` / tag `v9-before-production-go-live` |
| Release tag | `v9-production-weekly-live` |
| Acceptance tag | `v9-phase6h-production-go-live-validated` |

## Cloud Run Service (unchanged)

| Item | Value |
|------|-------|
| Name | `tech-cartography-v9-signal-watch` |
| Revision | `tech-cartography-v9-signal-watch-00003-br7` |
| Status | Ready |
| IAP | enabled |
| Anonymous access | denied |
| Image digest | `sha256:e99c9ceff68c4805dbb351256356a968ae95a2a9e0f3e198e5732cc1992b2e7f` |

## Cloud Run Job (production)

| Item | Value |
|------|-------|
| Name | `tech-cartography-v9-weekly-watch` |
| Image digest | `sha256:e99c9ceff68c4805dbb351256356a968ae95a2a9e0f3e198e5732cc1992b2e7f` |
| tasks / parallelism / maxRetries / timeout | 1 / 1 / 0 / 1800s |
| `V9_CLOUD_JOB_DRY_RUN` | `false` |
| Patent / Paper / Web | `true` / `true` / `true` |
| Patent queries | `patent_q01`, `patent_q02`, `patent_q05`, `patent_q06` |
| Paper query | `paper_q08` (max 5, time_range=all) |
| Web query | `gw_q001` (max 2, verification_limit=1) |
| BigQuery per-query cap | 2 TiB (`2199023255552`) |
| BigQuery cumulative cap | 6 TiB (`6597069766656`) |
| BigQuery max executions | 4 |
| BigQuery dry-run first | `true` |
| Email | enabled, `EMAIL_SEND_MODE=self_only` |
| SMTP secret | `tech-cartography-smtp-password:4` |
| Tavily secret | `tech-cartography-tavily-api-key:4` |

## Scheduler

| Item | Value |
|------|-------|
| Name | `tech-cartography-v9-weekly-watch-scheduler` |
| Region | `us-central1` |
| Schedule | `0 9 * * 1` (Monday 09:00) |
| Timezone | `Asia/Tokyo` |
| State after go-live | ENABLED |
| Target | v9 weekly watch Job run API |
| Auth SA | `tech-cartography-v9-scheduler@devops-ai-agent-hackathon-2026.iam.gserviceaccount.com` |
| Next scheduled run (JST) | 2026-07-06 09:00 JST |
| Next scheduled run (UTC) | 2026-07-06 00:00 UTC |

## Weekly delivery settings

| Item | Value |
|------|-------|
| enabled | `true` |
| revision after enable | 34 |
| weekday / hour / minute / timezone | MON / 9 / 0 / Asia/Tokyo |
| email_mode | `self_only` |

## First production execution (Scheduler trigger)

| Item | Value |
|------|-------|
| Scheduler manual trigger | accepted |
| Cloud Run execution | `tech-cartography-v9-weekly-watch-rflnz` |
| Triggered by | `tech-cartography-v9-scheduler@...` |
| Execution result | SUCCEEDED (1/1 tasks) |
| weekly_run_id | `cloud_weekly_job_20260704_181253` |
| overall_status | `success` |
| baseline_eligible | `true` |

### Provider results

| Provider | Status | Detail |
|----------|--------|--------|
| Patent / BigQuery | success | 4 queries executed; dry-run ok for all |
| BigQuery estimated bytes (total) | 1,044,246,991,288 | within 6 TiB cap |
| BigQuery processed bytes (total) | 1,044,246,991,288 | |
| BigQuery billed bytes (total) | 1,044,247,478,272 | within 6 TiB cap |
| Patent raw results | 300 | 75 per query |
| Paper / OpenAlex | success | 5 rows (`paper_q08`) |
| Web / Tavily | success | discovery=2, verification=1, grounding=0 |

### Artifacts

| Artifact | GCS path |
|----------|----------|
| weekly_diff.json | `gs://tech-cartography-v9-weekly-persist-1020686343587/weekly_runs/cloud_weekly_job_20260704_181253/weekly_diff.json` |
| weekly_digest.md | `gs://tech-cartography-v9-weekly-persist-1020686343587/weekly_runs/cloud_weekly_job_20260704_181253/weekly_digest.md` |
| integrated signals | 100 (deduplicated) |
| retrieval manifest | present |
| provider log | present |

### Email delivery

| Item | Value |
|------|-------|
| send_attempted | `true` |
| send_succeeded | `true` |
| send_count | 1 |
| mode | `self_only` |
| recipient allowlist | matched (masked in logs) |
| duplicate send guard | digest SHA256 guard active; new digest sent once |
| delivery log | `gs://tech-cartography-v9-weekly-persist-1020686343587/email_delivery_runs/email_delivery_20260704_181320_256403_8e25e16b/email_delivery_log.json` |

### Post-run safety

| Check | Result |
|-------|--------|
| cloud_job_locks residual | none |
| weekly_locks residual | none (directory placeholder only) |
| Scheduler state | ENABLED |
| weekly enabled | `true` |
| Job production config | maintained |

## Rollback procedure (on failure)

1. Pause scheduler:
   ```bash
   gcloud scheduler jobs pause tech-cartography-v9-weekly-watch-scheduler \
     --project=devops-ai-agent-hackathon-2026 --location=us-central1
   ```
2. Disable weekly delivery:
   ```bash
   V9_CLOUD_CHANGE_APPROVED=true PYTHONPATH=.:src python scripts/set_v9_cloud_weekly_enabled.py --disable
   ```
3. Restore Job safe settings (keep image digest and secret version 4):
   ```bash
   gcloud run jobs update tech-cartography-v9-weekly-watch \
     --project=devops-ai-agent-hackathon-2026 --region=us-central1 \
     --update-env-vars '^#^V9_CLOUD_JOB_DRY_RUN=true#V9_CLOUD_ENABLE_PATENT=false#V9_CLOUD_ENABLE_PAPER=false#V9_CLOUD_ENABLE_WEB_COMPANY=false#V9_ENABLE_EMAIL_SEND=false#DISABLE_EMAIL_SEND=true#EMAIL_SEND_MODE=preview'
   ```

## Out of scope (this phase)

- Shared password / study service
- User isolation / project isolation
- v7 / v8 changes
- Service IAP changes
- New credentials or image builds
