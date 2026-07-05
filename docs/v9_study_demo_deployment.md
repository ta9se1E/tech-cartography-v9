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

## Search Cost Preview Redeployment

Redeploy of the Step 1 BigQuery dry-run cost preview fix. Production resources were not modified. No live search acceptance was run during this stage.

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-05T05:28:26Z |
| Deployed at (JST) | 2026-07-05 14:28:26 JST |
| Expires at (UTC) | 2026-07-11T19:27:30Z |
| Expires at (JST) | 2026-07-12 04:27:30 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-utejl5os5a-uc.a.run.app |
| Revision | `tech-cartography-v9-study-demo-00004-hp5` |
| Previous revision | `tech-cartography-v9-study-demo-00003-wgl` |
| Rollback revision | `tech-cartography-v9-study-demo-00001-b48` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:550c060` |
| Image digest | `sha256:5d330034a48c908ac6b324aced800dca250e59e36cb5ca11ba6bfe8d7f594d93` |
| Cloud Build ID | `6a958a41-10f4-4509-83bf-76321a567196` |
| Password secret | `tech-cartography-v9-study-demo-password:2` |
| OpenAlex secret | `tech-cartography-v9-study-demo-openalex-api-key:1` |
| Tavily secret | `tech-cartography-v9-study-demo-tavily-api-key:1` |
| Password version 1 | ENABLED (not disabled) |

### Changes in this revision

- Step 1「検索計画を確認」で Patent BigQuery dry-run を実行し estimated bytes / GiB / TiB / 参考費用を表示
- Tavily credit hint を `unavailable_before_execution`（`null`）に修正
- Web exact phrase を quoted query 方式で反映

### Browser validation pending

User should confirm search plan preview in browser (no automated acceptance in this stage).

### Production unchanged (verified post-deploy)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`, IAP enabled, anonymous invoker denied
- Job config unchanged, no new execution
- Scheduler `ENABLED` (`0 9 * * 1`)
- Weekly delivery `enabled=true`
- Production bucket, secrets, and IAM unchanged

## Search Plan Normalization Redeployment

Redeploy of unified BigQuery execution gate, 6.25 USD/TiB cost display, validation cleanup, and Web exact-phrase dedupe. Production resources were not modified. No live search acceptance was run.

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-05T05:48:26Z |
| Deployed at (JST) | 2026-07-05 14:48:26 JST |
| Expires at (UTC) | 2026-07-11T19:27:30Z |
| Expires at (JST) | 2026-07-12 04:27:30 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-utejl5os5a-uc.a.run.app |
| Revision | `tech-cartography-v9-study-demo-00005-cwc` |
| Previous revision | `tech-cartography-v9-study-demo-00004-hp5` |
| Rollback revision | `tech-cartography-v9-study-demo-00001-b48` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:12df459` |
| Image digest | `sha256:d14a3a0cf2ca1fe1173c5a4984f5c5f7d50749ccff61be9e70be1de34fe002ff` |
| Cloud Build ID | `cbe2435c-4483-43f2-b06d-f4fe3d0e1077` |
| Password secret | `tech-cartography-v9-study-demo-password:2` |
| OpenAlex secret | `tech-cartography-v9-study-demo-openalex-api-key:1` |
| Tavily secret | `tech-cartography-v9-study-demo-tavily-api-key:1` |
| Password version 1 | ENABLED (not disabled) |

### Changes in this revision

- Unified `bigquery_execution_allowed` / `dry_run.execution_allowed` / `execution_performed` separation
- BigQuery reference cost at 6.25 USD/TiB across all cost fields
- Removed false `maximum_bytes_billed` validation warning when configured
- Web query dedupes exact phrase from keywords_en (quoted once)

### Browser validation pending

User should confirm search plan preview shows consistent execution flags and ~1.484 USD cost for sizing theme.

### Production unchanged (verified post-deploy)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`, IAP enabled, anonymous invoker denied
- Job config unchanged, no new execution
- Scheduler `ENABLED`
- Weekly delivery `enabled=true`
- Production bucket, secrets, and IAM unchanged

## Relevance Ranking Redeployment

Redeploy of Tier A/B/C/D relevance ranking, PAN/pitch material matching, relevance reason, score breakdown, Tier UI, Filter UI, and Export enhancements. Production resources were not modified. No live search or external provider execution was run.

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-05T06:35:23Z |
| Deployed at (JST) | 2026-07-05 15:35:23 JST |
| Expires at (UTC) | 2026-07-11T19:27:30Z |
| Expires at (JST) | 2026-07-12 04:27:30 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-utejl5os5a-uc.a.run.app |
| Revision | `tech-cartography-v9-study-demo-00006-6zf` |
| Previous revision | `tech-cartography-v9-study-demo-00005-cwc` |
| Rollback revision | `tech-cartography-v9-study-demo-00001-b48` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:938fb05` |
| Image digest | `sha256:0d2a3addf8cd60a0b7e4a2d9c96a809c4a214757c152c2b338528c078ed148d8` |
| Cloud Build ID | `ce72bcdc-6622-4061-b80d-1e64d29aa9b2` |
| Password secret | `tech-cartography-v9-study-demo-password:2` |
| OpenAlex secret | `tech-cartography-v9-study-demo-openalex-api-key:1` |
| Tavily secret | `tech-cartography-v9-study-demo-tavily-api-key:1` |
| Password version 1 | ENABLED (not disabled) |
| Git commit | `938fb05` |
| Tag (code) | `v9-study-demo-relevance-ranking-ready` |
| Tag (live candidate) | `v9-study-demo-relevance-ranking-live-candidate` |

### Changes in this revision

- Relevance tiering (A/B/C/D) with source-normalized scoring
- PAN priority and pitch/asphalt target-material mismatch display
- Tier-separated UI, filter controls, and enriched CSV/JSON/Markdown export
- Saved search history reload recomputes ranking locally from artifacts (no provider calls)

### Saved run for browser validation

- `study_demo_search_20260705_061319_e973e4c2`
- Load from history dropdown; ranking is recomputed in-memory without overwriting original artifacts

### Production unchanged (verified post-deploy)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`, IAP enabled, anonymous invoker denied
- Job config unchanged, no new execution
- Scheduler `ENABLED` (`0 9 * * 1`)
- Weekly delivery `enabled=true`
- Production bucket, secrets, and IAM unchanged

## Active Search Run Connection Deployment

Stage C4B deployment connecting saved temporary search runs to downstream tabs via shared Active Analysis Context. Production resources were not modified. No live search, external provider execution, or active_context Cloud write was performed during deploy.

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-05T07:34:14Z |
| Deployed at (JST) | 2026-07-05 16:34:14 JST |
| Expires at (UTC) | 2026-07-11T19:27:30Z |
| Expires at (JST) | 2026-07-12 04:27:30 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-1020686343587.us-central1.run.app |
| Revision | `tech-cartography-v9-study-demo-00007-6bw` |
| Previous revision | `tech-cartography-v9-study-demo-00006-6zf` |
| Rollback revision | `tech-cartography-v9-study-demo-00006-6zf` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:dd20eb2` |
| Image digest | `sha256:cd29f3bdf3f021e5af1d11bdaaf686f7471f6900909345d97a55dc7bea8094d7` |
| Cloud Build ID | `08a60f78-1700-4fcd-bccf-563317ba0723` |
| Build source cleanup | deleted |
| Service Account | `tech-cartography-v9-study-demo@devops-ai-agent-hackathon-2026.iam.gserviceaccount.com` |
| Min / max instances | 0 / 1 |
| Password secret | `tech-cartography-v9-study-demo-password:2` |
| OpenAlex secret | `tech-cartography-v9-study-demo-openalex-api-key:1` |
| Tavily secret | `tech-cartography-v9-study-demo-tavily-api-key:1` |
| Password version 1 | ENABLED (not disabled) |
| Password version 2 | in use |
| Git commit | `dd20eb2` |
| Tag (code) | `v9-study-demo-active-run-connection-ready` |
| Tag (live candidate) | `v9-study-demo-active-run-connection-live-candidate` |

### Active run connection

- Active Analysis Context code deployed (`analysis_context/active_context.json` schema, GCS generation precondition, shared loader)
- Downstream tabs (注目シグナル / 週次更新 / 監視プロファイル / ダイジェスト) use common loader when active context is set
- Legacy demo 12件: explicit button only; no automatic fallback when active context is unset
- **active_context initial write pending user action** (browser UI: 情報源タブ → 「この検索runを分析対象に設定」)

### Saved run available for browser validation

- `study_demo_search_20260705_061319_e973e4c2`
- All required artifacts present in demo bucket (search_request, provider_status, patent/paper/web results, integrated_signals, usage_metrics, search_status, search_report)
- ranked_count: 100 (integrated_signals.json)
- active_context: not yet created in demo bucket

### External API execution

- Deploy stage: 0 external API calls (BigQuery / OpenAlex / Tavily)
- Page display uses stored artifacts only until user initiates search

### Production unchanged (verified post-deploy)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`, IAP enabled, anonymous invoker denied
- Job config unchanged, no new execution during Stage C4B
- Scheduler `ENABLED` (`0 9 * * 1`, `Asia/Tokyo`)
- Weekly delivery `enabled=true`
- Production bucket, secrets, and IAM unchanged

### Browser validation pending

User should log in, select saved run `study_demo_search_20260705_061319_e973e4c2`, set as active analysis target, and confirm downstream tabs show consistent 100-item context. Final tag `v9-study-demo-active-run-connection-live-validated` awaits browser acceptance.
