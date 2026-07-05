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

## Active Run Selector Visibility Redeployment

Redeploy of the Active Run Selector UI fix: selector card moved immediately after search history dropdown (before execution summary). Production resources were not modified. No external API execution or active_context Cloud write during deploy.

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-05T08:41:15Z |
| Deployed at (JST) | 2026-07-05 17:41:15 JST |
| Expires at (UTC) | 2026-07-11T19:27:30Z |
| Expires at (JST) | 2026-07-12 04:27:30 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-1020686343587.us-central1.run.app |
| Revision | `tech-cartography-v9-study-demo-00008-gd7` |
| Previous revision | `tech-cartography-v9-study-demo-00007-6bw` |
| Rollback revision | `tech-cartography-v9-study-demo-00007-6bw` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:86ba8d1` |
| Image digest | `sha256:16b6b0fb15e3f7a6c3430a52aa4833a280ac6f70c56fe4fff35dc7220652d21e` |
| Cloud Build ID | `3b02f1ef-de6d-459c-bf73-be112bcf21be` |
| Build source cleanup | deleted |
| Image pre-push scan | PASS |
| Password secret | `tech-cartography-v9-study-demo-password:2` |
| OpenAlex secret | `tech-cartography-v9-study-demo-openalex-api-key:1` |
| Tavily secret | `tech-cartography-v9-study-demo-tavily-api-key:1` |
| Password version 1 | ENABLED (not disabled) |
| Git commit | `86ba8d1` |
| Tag (code) | `v9-study-demo-active-run-selector-ready` |
| Tag (live candidate) | `v9-study-demo-active-run-selector-live-candidate` |

### Selector visibility fix

- Active run selector rendered immediately after search history dropdown
- Independent of legacy「データ投入モード」; other data sources collapsed under expander
- **active_context initial write pending user action** (browser: checkbox + 「この検索runを分析対象に設定」)

### External API execution

- Deploy stage: 0 external API calls (BigQuery / OpenAlex / Tavily)
- Demo bucket only; no production bucket reference

### Production unchanged (verified post-deploy)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`, IAP enabled, anonymous invoker denied
- Job config unchanged, no new execution
- Scheduler `ENABLED` (`0 9 * * 1`, `Asia/Tokyo`)
- Weekly delivery `enabled=true`
- Production bucket, secrets, and IAM unchanged

### Browser validation pending

User should confirm selector card appears above execution summary after selecting saved run `study_demo_search_20260705_061319_e973e4c2`. Final validated tag not yet created.

## Active Context Counts and Download Keys Redeployment

Redeploy of Active Context UI fixes: banner tier counts resolved from enriched artifacts at display time (not stale cached 0/0/0/0); unique Streamlit download button keys per tab to prevent `StreamlitDuplicateElementId`. Production resources were not modified. No external API execution, active_context Cloud update, or snapshot write during deploy.

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-05T09:32:20Z |
| Deployed at (JST) | 2026-07-05 18:32:20 JST |
| Expires at (UTC) | 2026-07-11T19:27:30Z |
| Expires at (JST) | 2026-07-12 04:27:30 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-1020686343587.us-central1.run.app |
| Revision | `tech-cartography-v9-study-demo-00009-pbn` |
| Previous revision | `tech-cartography-v9-study-demo-00008-gd7` |
| Rollback revision | `tech-cartography-v9-study-demo-00008-gd7` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:a35070a` |
| Image digest | `sha256:a828d316f14663022a345db45ca5e3f96847d5e8a521e37e5f8a60a88895375e` |
| Cloud Build ID | `599736d0-9112-4a16-87a9-289837f38860` |
| Build source cleanup | deleted |
| Image pre-push scan | PASS |
| Password secret | `tech-cartography-v9-study-demo-password:2` |
| OpenAlex secret | `tech-cartography-v9-study-demo-openalex-api-key:1` |
| Tavily secret | `tech-cartography-v9-study-demo-tavily-api-key:1` |
| Password version 1 | ENABLED (not disabled) |
| Git commit | `a35070a` |
| Tag (code) | `v9-study-demo-active-context-ui-fix-ready` |
| Tag (live candidate) | `v9-study-demo-active-context-ui-fix-live-candidate` |

### Fixes deployed

- **Resolved context count fix**: banner and downstream loader recompute tier counts from enriched artifacts; cached `active_context.json` tier_counts may remain 0/0/0/0 until browser reload
- **Download button unique key fix**: all Study Demo download buttons use tab-scoped keys via `build_study_demo_download_key()`
- **Existing active_context preserved**: object `analysis_context/active_context.json` unchanged in demo bucket
- **Cache refresh pending browser action**: user may click「現在の分析対象を再読み込み」to refresh GCS cache metadata

### Active context (read-only verification)

- `active_search_run_id`: `study_demo_search_20260705_061319_e973e4c2`
- Object exists in demo bucket; content not modified during deploy

### External API execution

- Deploy stage: 0 external API calls (BigQuery / OpenAlex / Tavily)
- Demo bucket only; no production bucket reference

### Production unchanged (verified post-deploy)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`, IAP enabled, anonymous invoker denied
- Job config unchanged, no new execution
- Scheduler `ENABLED` (`0 9 * * 1`, `Asia/Tokyo`)
- Weekly delivery `enabled=true`
- Production bucket, secrets, and IAM unchanged

### Browser validation pending

User should confirm banner shows Tier A33/B13/C24/D30 (not 0/0/0/0), weekly/profile/digest tabs open without duplicate element errors, and optionally reload active context via browser. Final validated tag not yet created.

## Digest Event Contract Fix Redeployment

Redeploy of digest tab event contract fix: standardized `default_digest_events()` schema across all render paths; `normalize_digest_events()` on consumer; fixes `KeyError: 'save_digest_files'` when active temporary search run is used (weekly tab selection triggers digest render). Production resources were not modified. No external API execution, active_context update, snapshot write, or digest save during deploy.

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-05T10:12:19Z |
| Deployed at (JST) | 2026-07-05 19:12:19 JST |
| Expires at (UTC) | 2026-07-11T19:27:30Z |
| Expires at (JST) | 2026-07-12 04:27:30 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-1020686343587.us-central1.run.app |
| Revision | `tech-cartography-v9-study-demo-00010-ncr` |
| Previous revision | `tech-cartography-v9-study-demo-00009-pbn` |
| Rollback revision | `tech-cartography-v9-study-demo-00009-pbn` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:0229ecd` |
| Image digest | `sha256:bb13081f4e7befc7af1bc5a017c83c7e50e54e8094b4f3d791819f851550085f` |
| Cloud Build ID | `80d36c8a-8640-47e4-b009-bb2bfd3adee0` |
| Build source cleanup | deleted |
| Image pre-push scan | PASS |
| Password secret | `tech-cartography-v9-study-demo-password:2` |
| OpenAlex secret | `tech-cartography-v9-study-demo-openalex-api-key:1` |
| Tavily secret | `tech-cartography-v9-study-demo-tavily-api-key:1` |
| Password version 1 | ENABLED (not disabled) |
| Git commit | `0229ecd` |
| Tag (code) | `v9-study-demo-digest-event-contract-ready` |
| Tag (live candidate) | `v9-study-demo-digest-event-contract-live-candidate` |

### Fixes deployed

- **Digest event contract**: `ui_v9/study_demo_event_contracts.py` with `default_digest_events()` and `normalize_digest_events()`
- **save_digest_files KeyError fix**: temporary_search render path no longer returns wrong key names (`save_digest`, `email_dry_run`, `email_send`)
- **Consumer defense**: `signal_watch_app.py` wraps digest events with normalize and uses `.get()` for save action
- **Existing active_context preserved**: `analysis_context/active_context.json` unchanged in demo bucket

### Active context (read-only verification)

- `active_search_run_id`: `study_demo_search_20260705_061319_e973e4c2`
- Object exists in demo bucket; content not modified during deploy

### Unauthenticated smoke test

- HTTP 200, Streamlit SPA shell returned
- No Secret patterns or tab data exposed in initial HTML
- Password gate maintained (login required for app content)

### External API execution

- Deploy stage: 0 external API calls (BigQuery / OpenAlex / Tavily)
- Demo bucket only; no production bucket reference

### Production unchanged (verified post-deploy)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`, IAP enabled, anonymous invoker denied
- Job config unchanged, no new execution
- Scheduler `ENABLED` (`0 9 * * 1`, `Asia/Tokyo`)
- Weekly delivery `enabled=true`
- Production bucket, secrets, and IAM unchanged

### Browser validation pending

User should confirm weekly tab opens without crash, digest tab renders without `KeyError`, and active run context displays correctly. Final validated tag not yet created.

## External Source URL Resolution Fix Redeployment

Redeploy of external source URL resolution fix: standardized URL resolver for patent/paper/web signals; `st.link_button` renderer replaces empty-href Markdown links; `source_url` field propagation in active run adapter. Production resources were not modified. No external HTTP access, external API execution, active_context update, snapshot write, or digest save during deploy.

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-05T10:52:23Z |
| Deployed at (JST) | 2026-07-05 19:52:23 JST |
| Expires at (UTC) | 2026-07-11T19:27:30Z |
| Expires at (JST) | 2026-07-12 04:27:30 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-1020686343587.us-central1.run.app |
| Revision | `tech-cartography-v9-study-demo-00011-l85` |
| Previous revision | `tech-cartography-v9-study-demo-00010-ncr` |
| Rollback revision | `tech-cartography-v9-study-demo-00010-ncr` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:1e011e8` |
| Image digest | `sha256:208538c6414347034094fe524b7368e16b3f1d1337456f6cede597637e25636a` |
| Cloud Build ID | `1d84e545-2474-418b-99e6-4069186e6887` |
| Build source cleanup | deleted |
| Image pre-push scan | PASS |
| Password secret | `tech-cartography-v9-study-demo-password:2` |
| OpenAlex secret | `tech-cartography-v9-study-demo-openalex-api-key:1` |
| Tavily secret | `tech-cartography-v9-study-demo-tavily-api-key:1` |
| Password version 1 | ENABLED (not disabled) |
| Git commit | `1e011e8` |
| Tag (code) | `v9-study-demo-source-url-fix-ready` |
| Tag (live candidate) | `v9-study-demo-source-url-fix-live-candidate` |

### Fixes deployed

- **Empty href fix**: removed `[出典URLを開く]()` Markdown links that opened the Streamlit app itself
- **source_url field propagation**: adapter resolves `source_url` / publication number / DOI / canonical URL
- **External link renderer**: `ui_v9/study_demo_source_link.py` with `st.link_button` for valid external URLs only
- **Study Demo self URL rejection**: Cloud Run host URLs are not used as citation links
- **Existing active_context preserved**: `analysis_context/active_context.json` unchanged in demo bucket

### Active context (read-only verification)

- `active_search_run_id`: `study_demo_search_20260705_061319_e973e4c2`
- Object exists in demo bucket; content not modified during deploy

### Unauthenticated smoke test

- HTTP 200, Streamlit SPA shell returned
- No Secret patterns, active run ID, or signal content exposed in initial HTML
- Password gate maintained (login required for app content)
- No external citation URL fetch during smoke test

### External HTTP / API execution

- Deploy stage: 0 external HTTP requests (no HEAD/GET to citation URLs, DOI, Google Patents)
- Deploy stage: 0 external API calls (BigQuery / OpenAlex / Tavily)
- Demo bucket only; no production bucket reference

### Production unchanged (verified post-deploy)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`, IAP enabled, anonymous invoker denied
- Job config unchanged, no new execution
- Scheduler `ENABLED` (`0 9 * * 1`, `Asia/Tokyo`)
- Weekly delivery `enabled=true`
- Production bucket, secrets, and IAM unchanged

### Browser validation pending

User should confirm「出典URLを開く」/「引用元を開く」opens external patent/paper/web pages (not the Streamlit app), and missing URLs show「引用元URL未取得」without links. Final validated tag not yet created.
