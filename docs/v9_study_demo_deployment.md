# Tech Cartography v9 Study Demo Deployment Record

## Summary

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-04T19:28:07Z |
| Deployed at (JST) | 2026-07-05 04:28:07 JST |
| Expires at (UTC) | 2026-07-11T19:27:30Z |
| Expires at (JST) | 2026-07-12 04:27:30 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-utejl5os5a-uc.a.run.app |
| Revision | `tech-cartography-v9-study-demo-00001-b48` |
| Image digest | `sha256:8233e7a1741d9a83eadf0ff9e6250cabbd6f444aeb127443e2b1d71696ad49a4` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:c560647` |
| Service Account | `tech-cartography-v9-study-demo@devops-ai-agent-hackathon-2026.iam.gserviceaccount.com` |
| Bucket | `tech-cartography-v9-study-demo-1020686343587` |
| Password secret | `tech-cartography-v9-study-demo-password:1` |
| Min / max instances | 0 / 1 |
| Public method | `allUsers` → `roles/run.invoker` |
| Cloud Build ID | `d313da83-1e79-49b5-96a7-d44e40d4cc7e` |

## Isolation controls

- External providers disabled: BigQuery, OpenAlex, Tavily, Google Grounding
- Email disabled (`EMAIL_SEND_MODE=preview`, `V9_ENABLE_EMAIL_SEND=false`)
- No Cloud Run Job
- No Cloud Scheduler
- No SMTP / Tavily secret mounts
- Demo bucket mounted at `/mnt/v9_study_demo`; active data under `active/`

## Seed data

| Item | Value |
|------|-------|
| Source run ID | `cloud_weekly_job_20260704_181253` |
| Source bucket (read-only) | `tech-cartography-v9-weekly-persist-1020686343587` |
| Seed object count | 10 |
| Active object count | 9 |
| Sanitize validation | passed (metadata-only checks) |

## Production unchanged (verified)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`, IAP enabled
- Job production config maintained
- Scheduler `ENABLED` (`0 9 * * 1`, `Asia/Tokyo`)
- Weekly delivery `enabled=true`

## Cleanup (after study week)

```bash
cd /path/to/PatentScout_AI_v9_study_demo
bash scripts/cleanup_v9_study_demo.sh --plan
V9_STUDY_DEMO_CLEANUP_APPROVED=true bash scripts/cleanup_v9_study_demo.sh --apply
```

Do not modify production resources during cleanup.

## Browser Acceptance Validation

Validation status:
PASSED

Validated by:
User

Validation date:
2026-07-05 04:40:00 JST

Validated items:

- Public URLからpassword gateを表示できた
- ログイン前は6タブとデータを表示しなかった
- 誤ったパスワードではログインできなかった
- 正しい共通パスワードでログインできた
- 6タブを正常に表示できた
- 勉強会用バナーを表示できた
- 保存済み実データを表示できた
- 外部検索停止の案内を確認できた
- メール送信停止の案内を確認できた
- ログアウト後にpassword gateへ戻った
- ブラウザ上のエラーはなかった

Acceptance conclusion:
The isolated study demo is ready for the study session.

Expiry:
2026-07-12 04:27:30 JST

## Three-Source Search Deployment

Stage C2 deployment enabling Patent (BigQuery), Paper (OpenAlex), and Web (Tavily) live search on the study demo service only. Production resources were not modified.

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-05T04:56:00Z (approx.) |
| Deployed at (JST) | 2026-07-05 13:56:00 JST (approx.) |
| Expires at (UTC) | 2026-07-11T19:27:30Z |
| Expires at (JST) | 2026-07-12 04:27:30 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-utejl5os5a-uc.a.run.app |
| Revision | `tech-cartography-v9-study-demo-00003-wgl` |
| Rollback revision | `tech-cartography-v9-study-demo-00001-b48` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:4fbc9d4-c2fix` |
| Image digest | `sha256:2521be767bfefe788915f4b8820f77bf0bcb07369e7ae1b9c9491da6a8d50125` |
| Cloud Build ID | `7d91dad6-9f8d-41f4-8c1c-352cd6efdf2e` |
| Service Account | `tech-cartography-v9-study-demo@devops-ai-agent-hackathon-2026.iam.gserviceaccount.com` |
| Min / max instances | 0 / 1 |
| Password secret | `tech-cartography-v9-study-demo-password:2` |
| OpenAlex secret | `tech-cartography-v9-study-demo-openalex-api-key:1` |
| Tavily secret | `tech-cartography-v9-study-demo-tavily-api-key:1` |
| Password version 1 | ENABLED (not disabled; awaiting browser validation) |

### Search enablement

- Patent search: enabled (`V9_STUDY_DEMO_ENABLE_PATENT_SEARCH=true`)
- Paper search: enabled (`V9_STUDY_DEMO_ENABLE_PAPER_SEARCH=true`)
- Web search: enabled (`V9_STUDY_DEMO_ENABLE_WEB_SEARCH=true`)
- Email: disabled
- Google Grounding: disabled
- Demo bucket only: `tech-cartography-v9-study-demo-1020686343587`

### Demo SA IAM (added for Stage C2)

- `roles/bigquery.jobUser` (project) — Google Patents public dataset queries only
- `roles/secretmanager.secretAccessor` on `tech-cartography-v9-study-demo-openalex-api-key`
- `roles/secretmanager.secretAccessor` on `tech-cartography-v9-study-demo-tavily-api-key`
- Existing password secret accessor maintained (secret-scoped)

### Three-source acceptance

| Item | Value |
|------|-------|
| Acceptance search_run_id | `study_demo_search_20260705_045754_8ce2ea74` |
| Overall status | `success` |
| Patent provider | success, 50 results |
| Paper provider | success, 11 results |
| Web provider | success, 10 results |
| Integrated signals | 61 |
| Keyword suggestions | 15 |
| BigQuery estimated bytes | 261,061,747,822 |
| BigQuery processed bytes | 261,061,747,822 |
| BigQuery billed bytes | 261,061,869,568 |
| BigQuery reference cost (USD) | ~1.48 |
| OpenAlex request count | 1 |
| OpenAlex pagination count | 0 |
| Tavily request count | 1 |
| Tavily credits (recorded) | 0 |
| Artifact safety | passed (no secret/API key/password leak) |

### Production unchanged (verified post-acceptance)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`, IAP enabled, anonymous invoker denied
- Job config unchanged, no new execution during Stage C2
- Scheduler `ENABLED` (`0 9 * * 1`)
- Weekly delivery `enabled=true`
- Production bucket, secrets, and IAM unchanged

### Browser validation pending

Password secret version 1 remains ENABLED. After browser confirmation (new password login, old password failure, search UI), disable version 1 in a separate stage.

### Disable search (study demo only)

```bash
bash scripts/disable_v9_study_demo_search.sh --plan
V9_STUDY_DEMO_SEARCH_DISABLE_APPROVED=true bash scripts/disable_v9_study_demo_search.sh --apply
```
