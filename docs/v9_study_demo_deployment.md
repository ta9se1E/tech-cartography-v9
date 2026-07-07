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

## Google Patents Canonical URL Fix Deployment

Redeploy of Google Patents URL canonicalization: dashed publication numbers in `patents.google.com/patent/` paths are normalized to compact form (e.g. `US-2020-378036-A1` → `US2020378036A1`). Paper and Web URLs unchanged. Production resources were not modified. No external HTTP access or external API execution during deploy.

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-05T11:33:03Z |
| Deployed at (JST) | 2026-07-05 20:33:03 JST |
| Expires at (UTC) | 2026-07-11T19:27:30Z |
| Expires at (JST) | 2026-07-12 04:27:30 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-1020686343587.us-central1.run.app |
| Revision | `tech-cartography-v9-study-demo-00012-9sm` |
| Previous revision | `tech-cartography-v9-study-demo-00011-l85` |
| Rollback revision | `tech-cartography-v9-study-demo-00011-l85` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:5abafba` |
| Image digest | `sha256:39c6512bf9e9903f39b224bb2c9d9787d0d0676723d00f0900dd37cfdc4a6df3` |
| Cloud Build ID | `f56a237d-6e87-46d1-b725-f89d12cd5263` |
| Build source cleanup | deleted |
| Image pre-push scan | PASS |
| Password secret | `tech-cartography-v9-study-demo-password:2` |
| OpenAlex secret | `tech-cartography-v9-study-demo-openalex-api-key:1` |
| Tavily secret | `tech-cartography-v9-study-demo-tavily-api-key:1` |
| Password version 1 | ENABLED (not disabled) |
| Git commit (fix) | `5abafba` |
| Tag (code) | `v9-study-demo-google-patents-url-fix-ready` |
| Tag (live candidate) | `v9-study-demo-google-patents-url-fix-live-candidate` |

### Fixes deployed

- **Dashed publication number normalization**: `normalize_google_patents_url()` extracts `/patent/<id>`, URL-decodes, strips hyphens/spaces, rebuilds canonical URL
- **Compact URL preservation**: already-compact Google Patents URLs unchanged
- **Paper/Web unchanged**: DOI and web canonical URLs not rewritten
- **Existing active_context preserved**: `analysis_context/active_context.json` unchanged in demo bucket

### Active context (read-only verification)

- `active_search_run_id`: `study_demo_search_20260705_061319_e973e4c2`
- Object exists in demo bucket; content not modified during deploy

### Unauthenticated smoke test

- HTTP 200, Streamlit SPA shell returned
- No Secret patterns or active run content exposed in initial HTML
- Password gate maintained
- No Google Patents URL fetch during smoke test

### External HTTP / API execution

- Deploy stage: 0 external HTTP requests
- Deploy stage: 0 external API calls (BigQuery / OpenAlex / Tavily)
- Demo bucket only; no production bucket reference

### Production unchanged (verified post-deploy)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`, IAP enabled, anonymous invoker denied
- Job config unchanged, no new execution
- Scheduler `ENABLED` (`0 9 * * 1`, `Asia/Tokyo`)
- Weekly delivery `enabled=true`
- Production bucket, secrets, and IAM unchanged

### Browser validation pending

User should confirm patent「出典URLを開く」opens `https://patents.google.com/patent/US2020378036A1/en` style URLs (not dashed paths). Final validated tag not yet created.

## Theme Lineage and Review Proposal Deployment

Stage C5B-1 deploy of Theme → Watch Profile → Search Plan → Run lineage UI and human review improvement proposal UI. No Theme/Profile/Plan/Review/Proposal Cloud writes during deploy. No external search or live small-search E2E. Production resources were not modified.

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-05T13:22:50Z |
| Deployed at (JST) | 2026-07-05 22:22:50 JST |
| Expires at (UTC) | 2026-07-11T19:27:30Z |
| Expires at (JST) | 2026-07-12 04:27:30 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-1020686343587.us-central1.run.app |
| Revision | `tech-cartography-v9-study-demo-00013-vtl` |
| Previous revision | `tech-cartography-v9-study-demo-00012-9sm` |
| Rollback revision | `tech-cartography-v9-study-demo-00012-9sm` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:b888397` |
| Image digest | `sha256:12c42c7a554bc6e31dc37ffb3abc2667936faa4761852cdbfc65bd15ad5ac89c` |
| Cloud Build ID | `64f2a86c-4af2-4579-af33-11a1652a3b29` |
| Build source cleanup | deleted |
| Image pre-push scan | PASS |
| Password secret | `tech-cartography-v9-study-demo-password:2` |
| OpenAlex secret | `tech-cartography-v9-study-demo-openalex-api-key:1` |
| Tavily secret | `tech-cartography-v9-study-demo-tavily-api-key:1` |
| Password version 1 | ENABLED (not disabled) |
| Git commit (code) | `b888397` |
| Tag (code) | `v9-study-demo-theme-lineage-review-proposals-ready` |
| Tag (live candidate) | `v9-study-demo-theme-lineage-review-proposals-live-candidate` |

### Features deployed

- **Theme lineage UI**: standard theme vs active analysis target separation, run_origin, lineage_status banner
- **Temporary run promotion**:「この検索条件からテーマ案を作成」draft-only path (no overwrite)
- **Review UI**: decision / reason_codes / comment with schema v2
- **Proposal UI**: deterministic improvement proposals, human approval only, observation-only below threshold
- **Lineage banner**: shared across attention / weekly / profile / digest tabs

### Active context (read-only verification)

- `active_search_run_id`: `study_demo_search_20260705_061319_e973e4c2`
- GCS object unchanged during deploy (no lineage fields written to Cloud; runtime enrichment only)

### Cloud data writes during deploy

- Theme / Watch Profile / Search Plan: **0**
- Review / Proposal / Profile draft: **0**
- active_context / snapshot / digest: **0**

### Unauthenticated smoke test

- HTTP 200, Streamlit SPA shell returned
- No Secret patterns or theme/run/signal content in initial HTML
- Password gate maintained

### External HTTP / API execution

- Deploy stage: 0 external HTTP requests
- Deploy stage: 0 external API calls (BigQuery / OpenAlex / Tavily)

### Production unchanged (verified post-deploy)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`, IAP enabled
- Scheduler `ENABLED` (`0 9 * * 1`, `Asia/Tokyo`)
- Production bucket, secrets, and IAM unchanged

### Browser validation pending

User should confirm Theme tab separation, lineage banner, review/proposal UI, Tier counts, URLs, weekly, digest. Stage C5B-2 live 5/5/5 search not yet executed. Final validated tag not yet created.

## Theme Draft Review and Save-as-New UI Deployment

Stage C5B-1.2 deploy of Theme draft review/editor UI and save-as-new workflow. Draft content is session-only (`persist_to_cloud=false`); no Theme/Profile/Plan/Theme draft Cloud writes during deploy. No external search or live small-search E2E. Production resources were not modified.

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-05T13:57:59Z |
| Deployed at (JST) | 2026-07-05 22:57:59 JST |
| Expires at (UTC) | 2026-07-11T19:27:30Z |
| Expires at (JST) | 2026-07-12 04:27:30 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-1020686343587.us-central1.run.app |
| Revision | `tech-cartography-v9-study-demo-00014-mwk` |
| Previous revision | `tech-cartography-v9-study-demo-00013-vtl` |
| Rollback revision | `tech-cartography-v9-study-demo-00013-vtl` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:45067f9` |
| Image digest | `sha256:2d58310cb02c6952c98952a711a36f92ee5eb9a6e60c4a47012cc73f4da6f026` |
| Cloud Build ID | `e64369f3-12f3-4f92-93b5-12599ec75e4b` |
| Build source cleanup | deleted |
| Image pre-push scan | PASS |
| Password secret | `tech-cartography-v9-study-demo-password:2` |
| OpenAlex secret | `tech-cartography-v9-study-demo-openalex-api-key:1` |
| Tavily secret | `tech-cartography-v9-study-demo-tavily-api-key:1` |
| Password version 1 | ENABLED (not disabled) |
| Git commit (code) | `45067f9` |
| Tag (code) | `v9-study-demo-theme-draft-ui-ready` |
| Tag (live candidate) | `v9-study-demo-theme-draft-ui-live-candidate` |

### Features deployed

- **Theme draft section D**:「作成した未保存テーマ案」status card with provenance and impact indicators
- **Draft-only editor**: separate widget keys (`theme_draft_{draft_id}_*`), sizing content from active run only
- **Draft actions**: keep changes (session), save-as-new (session-only, `persist_to_cloud=false`), discard
- **Old Search Plan warning**: saved standard theme plan shown as unconnected to draft
- **Saved theme selector**: multiple themes list without auto-search or active context change
- **Standard theme actions clarified**: no confusion with draft save path

### Active context (read-only verification)

- `active_search_run_id`: `study_demo_search_20260705_061319_e973e4c2`
- GCS object `analysis_context/active_context.json` unchanged during deploy

### Cloud data writes during deploy

- Theme / Watch Profile / Search Plan / Theme draft: **0**
- Review / Proposal / Profile draft: **0**
- active_context / snapshot / digest: **0**

### Unauthenticated smoke test

- HTTP 200, Streamlit SPA shell returned
- No Secret patterns or theme/run/signal content in initial HTML
- Password gate maintained

### External HTTP / API execution

- Deploy stage: 0 external HTTP requests
- Deploy stage: 0 external API calls (BigQuery / OpenAlex / Tavily)

### Production unchanged (verified post-deploy)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`, IAP enabled
- Scheduler `ENABLED` (`0 9 * * 1`, `Asia/Tokyo`)
- Production bucket, secrets, and IAM unchanged

### Browser validation pending

User should confirm draft section D, draft editor with sizing content, save-as-new/discard buttons, old plan warning, and Tier/URL/weekly/digest regression. Stage C5B-2 (Cloud save + Watch Profile + Search Plan + 5/5/5 live search) not yet executed. Final validated tag not yet created.

## Theme Draft Mapping and Old Plan Isolation Deployment

Stage C5B-1.4 deploy of theme draft mapping pipeline, language classification, explicit draft review, old Search Plan isolation, and UI cleanup. No Theme/Profile/Plan/Theme draft Cloud writes during deploy. No external search or live small-search E2E. Production resources were not modified.

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-05T14:23:33Z |
| Deployed at (JST) | 2026-07-05 23:23:33 JST |
| Expires at (UTC) | 2026-07-11T19:27:30Z |
| Expires at (JST) | 2026-07-12 04:27:30 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-1020686343587.us-central1.run.app |
| Revision | `tech-cartography-v9-study-demo-00015-4v2` |
| Previous revision | `tech-cartography-v9-study-demo-00014-mwk` |
| Rollback revision | `tech-cartography-v9-study-demo-00014-mwk` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:a52e4c0` |
| Image digest | `sha256:64e78646780064d37dc49f5907d9abf18e06549d3133fa3865a3e2dc90d6b405` |
| Cloud Build ID | `bc3ecc4e-29d4-4abe-bcd0-84f3d18acd99` |
| Build source cleanup | deleted |
| Image pre-push scan | PASS |
| Password secret | `tech-cartography-v9-study-demo-password:2` |
| OpenAlex secret | `tech-cartography-v9-study-demo-openalex-api-key:1` |
| Tavily secret | `tech-cartography-v9-study-demo-tavily-api-key:1` |
| Password version 1 | ENABLED (not disabled) |
| Git commit (code) | `a52e4c0` |
| Tag (code) | `v9-study-demo-theme-draft-mapping-fix-ready` |
| Tag (live candidate) | `v9-study-demo-theme-draft-mapping-fix-live-candidate` |

### Features deployed

- **Theme draft mapping pipeline**: semantic bucket classification, language detection, exact phrase extraction, alias suggestions with provenance
- **Language classification fix**: English exclude terms routed to `exclude_en`, not `exclude_ja`
- **Theme name normalization**: concise suggested name; full text kept in description
- **Explicit draft review**: `not_reviewed` default; checkbox + confirm button; save blocked until reviewed
- **Old Search Plan isolation**: collapsed expander, scoped success messages, draft-unconnected warnings
- **UI cleanup**: 保存予定Theme ID labels, technical signature expander, toast-only draft creation, no `keyboard_arrow_right` strings

### Mapping validation (fixture pre-deploy)

- `language_bucket_mismatch`: 0
- `old_theme_contamination`: 0
- `blocking_error_count`: 0
- `suggested_theme_name`: PAN系炭素繊維用サイジング剤の組成・付与・乾燥条件

### Active context (read-only verification)

- `active_search_run_id`: `study_demo_search_20260705_061319_e973e4c2`
- GCS object `analysis_context/active_context.json` unchanged during deploy

### Cloud data writes during deploy

- Theme / Watch Profile / Search Plan / Theme draft: **0**
- Review / Proposal / Profile draft: **0**
- active_context / snapshot / digest: **0**

### Unauthenticated smoke test

- HTTP 200, Streamlit SPA shell returned
- No Secret patterns or theme/run/signal content in initial HTML
- Password gate maintained

### External HTTP / API execution

- Deploy stage: 0 external HTTP requests
- Deploy stage: 0 external API calls (BigQuery / OpenAlex / Tavily)

### Production unchanged (verified post-deploy)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`, IAP enabled
- Scheduler `ENABLED` (`0 9 * * 1`, `Asia/Tokyo`)
- Production bucket, secrets, and IAM unchanged

### Browser validation pending

User should confirm short theme name, JA/EN keyword buckets, alias candidate approval, explicit draft review, old plan isolation, and Tier/URL/weekly/digest regression. Stage C5B-2 (Theme Cloud save + Watch Profile + Search Plan + 5/5/5 live search) not yet executed. Final validated tag not yet created.

## Localized Theme Name and Explicit Exclusion Fix Deployment

Stage C5B-1.4.1 deploy of localized theme name sanitization and explicit exclusion provenance preservation. No Theme/Profile/Plan/Theme draft Cloud writes during deploy. No external search or live small-search E2E. Production resources were not modified.

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-05T14:36:13Z |
| Deployed at (JST) | 2026-07-05 23:36:13 JST |
| Expires at (UTC) | 2026-07-11T19:27:30Z |
| Expires at (JST) | 2026-07-12 04:27:30 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-1020686343587.us-central1.run.app |
| Revision | `tech-cartography-v9-study-demo-00016-zfs` |
| Previous revision | `tech-cartography-v9-study-demo-00015-4v2` |
| Rollback revision | `tech-cartography-v9-study-demo-00015-4v2` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:4bd62fe` |
| Image digest | `sha256:af0898808080bd5621babc51ec85b765aa29f0127c3c4c52497bd65c79d2ba4d` |
| Cloud Build ID | `5e6945a9-fbdd-464e-8bec-90e32c9d9292` |
| Build source cleanup | deleted |
| Image pre-push scan | PASS |
| Password secret | `tech-cartography-v9-study-demo-password:2` |
| OpenAlex secret | `tech-cartography-v9-study-demo-openalex-api-key:1` |
| Tavily secret | `tech-cartography-v9-study-demo-tavily-api-key:1` |
| Password version 1 | ENABLED (not disabled) |
| Git commit (code) | `4bd62fe` |
| Tag (code) | `v9-study-demo-theme-name-exclusion-fix-ready` |
| Tag (live candidate) | `v9-study-demo-theme-name-exclusion-fix-live-candidate` |

### Features deployed

- **Dry燥条件 fix**: Japanese theme name sanitization prevents mixed-script `Dry燥` corruption; suggested name is `PAN系炭素繊維用サイジング剤の組成・付与・乾燥条件`
- **Explicit exclusion provenance**: `paper sizing`, `starch sizing`, `activated carbon` treated as confirmed `exclude_en` with `provenance=explicit_request_field`
- **Candidate exclusion**: explicit request terms not shown in alias candidate section or adoption checkboxes
- **Provenance priority**: user_edited > explicit_request_field > exact_theme_text_match > legacy_import > canonical_alias_suggestion

### Mapping validation (fixture pre-deploy)

- `suggested_theme_name`: PAN系炭素繊維用サイジング剤の組成・付与・乾燥条件
- `explicit_exclusion_count`: 4 (includes textile)
- `explicit_exclusion_candidate_count`: 0
- `language_bucket_mismatch`: 0
- `old_theme_contamination`: 0
- `blocking_error_count`: 0

### Active context (read-only verification)

- `active_search_run_id`: `study_demo_search_20260705_061319_e973e4c2`
- GCS object `analysis_context/active_context.json` unchanged during deploy

### Cloud data writes during deploy

- Theme / Watch Profile / Search Plan / Theme draft: **0**
- Review / Proposal / Profile draft: **0**
- active_context / snapshot / digest: **0**

### External HTTP / API execution

- Deploy stage: 0 external HTTP requests
- Deploy stage: 0 external API calls (BigQuery / OpenAlex / Tavily)

### Production unchanged (verified post-deploy)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`, IAP enabled
- Production bucket, secrets, and IAM unchanged

### Browser validation pending

User should confirm suggested theme name without `Dry燥条件`, full description preserved, three explicit English exclusions in confirmed exclude section (not candidates), draft review initial state, old Search Plan isolation, and Tier/URL/weekly/digest regression. Stage C5B-2 not yet executed. Final validated tag not yet created.

## Live Watch Profile Lineage UI Repair

Stage C5B-2.1 repair to connect saved Theme / Watch Profile / Search Plan / Search Run artifacts to the Study Demo browser UI without re-running external search.

### Root cause

1. **Cloud Run code lag**: revision `00016-zfs` lacked GCS lineage loader/hydration code from C5B-2 (`04898b0`, `d1e513f`).
2. **`context_type` / `run_origin` mismatch**: Active Context stored `context_type=temporary_search` with `run_origin=watch_profile`, causing validation failure and partial lineage display.
3. **Loader overwrite bug**: `enrich_active_context_with_lineage()` rebuilt lineage from `search_request.json` (which uses `source_search_plan_id` not `search_plan_id`) and overwrote existing `source_*` refs with `None`, yielding `lineage_status=partial`.
4. **UI fixture-only state**: Theme selector and Search Plan Preview used session fixtures (`theme_default_saved`) instead of GCS saved artifacts.

### Deployment

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-05T15:26:27Z |
| Deployed at (JST) | 2026-07-06 00:26:27 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-1020686343587.us-central1.run.app |
| Revision | `tech-cartography-v9-study-demo-00018-wrf` |
| Rollback revision | `tech-cartography-v9-study-demo-00016-zfs` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:8446055` |
| Image digest | `sha256:748b33b4b7c1e7e562e4319cf256fbe89bb69cde9489560c57366d7ac2bcb9cc` |
| Cloud Build ID | `9f722b85-cb4c-44ce-b68b-913bd1393e45` |
| Git commit (code) | `b60ad96` (+ `8446055` load/save normalization) |
| Tag (code) | `v9-study-demo-live-lineage-fix-ready` |
| Tag (live candidate) | `v9-study-demo-live-lineage-fix-live-candidate` |

### Code changes

- **`study_demo_live_lineage_loader.py`**: GCS Theme/Profile/Plan enumeration and session hydration
- **`enrich_active_context_with_lineage()`**: preserve existing `source_*` refs; extract from `search_request` `source_*` fields
- **`context_type=watch_profile`**: formally allowed; normalize on GCS load
- **Theme selector**: lists GCS themes + default fixture; auto-selects active `source_theme_id`
- **Search Plan Preview**: resolves plan from active lineage; shows 5/5/5 limits and `validation_status=ready_for_execution`
- **Legacy defect-control plan UI**: hidden when live lineage is connected

### Active Context normalization (post-deploy apply)

| Field | Value |
|-------|-------|
| `active_search_run_id` | `study_demo_search_20260705_145711_c06e0a1b` |
| `context_type` | `watch_profile` |
| `run_origin` | `watch_profile` |
| `source_theme_id` | `theme_6d2dfb753f7e` |
| `source_watch_profile_id` | `wp_theme_6d2dfb753f7e` |
| `source_search_plan_id` | `plan_wp_theme_6d2dfb753f7e` |
| `lineage_status` | `connected` |
| `active_context_generation` | 2 (was 1) |
| Rollback active run ID | `study_demo_search_20260705_061319_e973e4c2` |

### Artifact verification (read-only)

- Theme `theme_6d2dfb753f7e` v1 saved, signature match
- Watch Profile `wp_theme_6d2dfb753f7e` saved, signature match
- Search Plan `plan_wp_theme_6d2dfb753f7e` ready_for_execution, limits 5/5/5
- Search Run integrated=15, Tier A/B/C/D=3/2/3/7
- No artifact body rewrites during repair

### External search / production

- External API calls: **0**
- Production resources modified: **false**
- Scheduler / email / IAM / secrets: unchanged

### Browser acceptance pending

User should confirm new sizing Theme selected, both themes in list, connected lineage across all tabs, Search Plan Preview 5/5/5, no partial/部分接続 display, integrated=15, Tier=3/2/3/7. Validated tag not yet created.

## Hackathon Demo P0 UI Consistency Deployment

Stage C5B-3B deploy of P0 UI/state consistency fixes (Theme selector/editor sync, information source active run state, canonical metrics) to Study Demo only.

### Deployment

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-07T13:09:00Z |
| Deployed at (JST) | 2026-07-07 22:09:00 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-1020686343587.us-central1.run.app |
| Revision | `tech-cartography-v9-study-demo-00019-8zp` |
| Rollback revision | `tech-cartography-v9-study-demo-00018-wrf` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:5183415` |
| Image digest | `sha256:ba309d1b564cdc99dc176c1f9b284552afa24b8d2cef5ec76916471ec98808c2` |
| Cloud Build ID | `49fbba74-e3c2-4829-abce-f036d1f5e561` |
| Build source cleanup | deleted |
| Git commit (code) | `5183415` |
| Tag (code) | `v9-study-demo-hackathon-p0-ready` |
| Tag (live candidate) | `v9-study-demo-hackathon-p0-live-candidate` |

### Features deployed

- Theme selector / editor sync (`selected_saved_theme_id` SSOT, versioned widget keys, save guard)
- Active Theme auto-selection from watch_profile Active Context
- Information source tab: current run state from Active Context / artifacts (B region); legacy isolated (C region)
- Canonical run metrics (`study_demo_run_metrics.py`) with unknown-metric handling and consistency validation
- Legacy source state isolation (`手動アップロード・旧データ投入機能`, default collapsed)

### Data preservation (read-only verified post-deploy)

| Field | Value |
|-------|-------|
| `active_context_generation` | 2 (unchanged) |
| `active_search_run_id` | `study_demo_search_20260705_145711_c06e0a1b` |
| `context_type` | `watch_profile` |
| `run_origin` | `watch_profile` |
| `source_theme_id` | `theme_6d2dfb753f7e` |
| `source_watch_profile_id` | `wp_theme_6d2dfb753f7e` |
| `source_search_plan_id` | `plan_wp_theme_6d2dfb753f7e` |
| `lineage_status` | `connected` |
| `provider_counts` | Patent 5 / Paper 5 / Web 5 |
| `tier_counts` | A 3 / B 2 / C 3 / D 7 |
| integrated signals | 15 |

- No Theme / Watch Profile / Search Plan / Search Run artifact writes
- No Active Context update (GCS `Update time` unchanged since 2026-07-05)
- External API execution: **0**
- Cloud data writes: **0**

### Service configuration (unchanged)

- Service Account: `tech-cartography-v9-study-demo@devops-ai-agent-hackathon-2026.iam.gserviceaccount.com`
- Password secret: version **2**
- OpenAlex secret: version **1**
- Tavily secret: version **1**
- min instances: 0 / max instances: 1
- Public password gate: maintained (`allUsers` invoker + in-app password)
- email: false

### Production unchanged (verified post-deploy)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`, IAP enabled
- Scheduler `tech-cartography-v9-weekly-watch-scheduler`: ENABLED, `0 9 * * 1` Asia/Tokyo
- Production weekly `enabled=true`
- Production bucket, secrets, IAM, and jobs unchanged

### Unauthenticated smoke test

- HTTP 200, Streamlit SPA bootstrap detected
- No Theme/Run/Signal content or secret patterns in unauthenticated response

### Browser acceptance pending

User should confirm Theme selector/editor match sizing Theme, information source current section shows saved standard search run with provider success 5/5/5, lineage connected, integrated=15, Tier=3/2/3/7, no demo/準備中/none/0 misdisplay in current section, legacy expander isolated. Validated tag not yet created.

## Hackathon Demo Simple Mode Deployment

Stage C5B-4B deploy of progressive disclosure Simple Mode UI to Study Demo only.

### Deployment

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-07T13:57:58Z |
| Deployed at (JST) | 2026-07-07 22:57:58 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-1020686343587.us-central1.run.app |
| Revision | `tech-cartography-v9-study-demo-00020-bg2` |
| Rollback revision | `tech-cartography-v9-study-demo-00019-8zp` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:1a5848f` |
| Image digest | `sha256:70e7e3ab8a806e197819e4f6f3b2c08b9454d1540c86c730742c1be58b4b3d41` |
| Cloud Build ID | `b07394a3-cb83-4039-8cca-945fa7fb0e27` |
| Build source cleanup | deleted |
| Git commit (code) | `1a5848f` |
| Tag (code) | `v9-study-demo-simple-ui-ready` |
| Tag (live candidate) | `v9-study-demo-simple-ui-live-candidate` |

### UI mode

| Setting | Value |
|---------|-------|
| `V9_UI_MODE` | `simple` (explicit on Cloud Run) |
| Compact header | enabled |
| Compact context bar | enabled (once per page) |
| Advanced mode | preserved in code (`V9_UI_MODE=advanced`) |
| User-facing mode toggle | none |

### Features deployed

- Theme page simplification (card + collapsed search conditions, editor on demand)
- Source page simplification (provider cards, collapsed history/query, new search on button)
- Signal Top3 deduplication with remaining signals collapsed
- Legacy tools hidden in simple mode
- Weekly / Profile / Digest compact views
- Download limited to 2 user-facing options in simple Digest tab

### Data preservation (read-only verified post-deploy)

| Field | Value |
|-------|-------|
| `active_context_generation` | 2 (unchanged) |
| `active_search_run_id` | `study_demo_search_20260705_145711_c06e0a1b` |
| `context_type` | `watch_profile` |
| `run_origin` | `watch_profile` |
| `source_theme_id` | `theme_6d2dfb753f7e` |
| `source_watch_profile_id` | `wp_theme_6d2dfb753f7e` |
| `source_search_plan_id` | `plan_wp_theme_6d2dfb753f7e` |
| `lineage_status` | `connected` |
| `provider_counts` | Patent 5 / Paper 5 / Web 5 |
| `tier_counts` | A 3 / B 2 / C 3 / D 7 |

- No Theme / Watch Profile / Search Plan / Search Run artifact writes
- No Active Context update (GCS `Update time` unchanged since 2026-07-05)
- External API execution: **0**
- Cloud data writes: **0**

### Service configuration (unchanged)

- Service Account: `tech-cartography-v9-study-demo@devops-ai-agent-hackathon-2026.iam.gserviceaccount.com`
- Password secret: version **2**
- OpenAlex secret: version **1**
- Tavily secret: version **1**
- min instances: 0 / max instances: 1
- Public password gate: maintained
- email: false

### Production unchanged (verified post-deploy)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`
- Scheduler ENABLED, `0 9 * * 1` Asia/Tokyo
- Production weekly `enabled=true`

### Unauthenticated smoke test

- HTTP 200, Streamlit SPA bootstrap detected
- No Theme/Run/Signal content or secret patterns in unauthenticated response

### Browser acceptance pending

User should confirm single header/context bar, Theme/Sources within ~2 screens, Signals Top3 only with remaining collapsed, no legacy/internal metrics in simple view, Download ≤2, lineage/15件/Tier maintained, no external API on page load. Validated tag not yet created.

## Research Value and Human-Facing Safety Deployment

Stage C5B-5C deploy of deterministic research value synthesis (C5B-5A) and human-facing baseline / digest / review / proposal safety (C5B-5B) to Study Demo only. No Theme/Profile/Plan/Run/Review/Proposal/snapshot/digest Cloud writes during deploy. No external search or production changes.

### Deployment

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-07T14:58:57Z |
| Deployed at (JST) | 2026-07-07 23:58:57 JST |
| Expires at (UTC) | 2026-07-11T19:27:30Z |
| Expires at (JST) | 2026-07-12 04:27:30 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-utejl5os5a-uc.a.run.app |
| Revision | `tech-cartography-v9-study-demo-00021-x27` |
| Rollback revision | `tech-cartography-v9-study-demo-00020-bg2` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:81bfa61` |
| Image digest | `sha256:c1bffbc854e030c825f6a6ebe12c77a28d7305e347d128e2a77090917246e477` |
| Cloud Build ID | `9961ebf7-0cec-405d-9c99-d641aa8ad3f2` |
| Build source cleanup | deleted |
| Image pre-push scan | PASS |
| Git commit (code) | `81bfa61` |
| Tag (code) | `v9-study-demo-human-facing-safety-ready` |
| Tag (live candidate) | `v9-study-demo-human-facing-safety-live-candidate` |

### Features deployed

- **Deterministic research value synthesis**: theme-axis extraction, role-diverse Top3, research_value / questions / readout cards
- **Top3 role diversity**: 処方・工程候補 / 物性エビデンス / 新規処方仮説
- **Initial Baseline semantics**: Top3 heading「今回まず確認する3件」, Initial Baseline badge, no diff 0 counts on first run
- **Human-facing Digest**: heading「今週のR&Dシグナル」, no run ID / Python dict / internal tokens in simple view
- **Unreviewed default**: review initial state「未判断」, save blocked until decision selected
- **Proposal threshold**: insufficient-review message; no provider-priority proposals below threshold
- **Internal token hidden**: sizing:title, aqueous:abstract, raw Tier dict suppressed in simple view
- **Low relevance labels**: Tier A=優先確認, B=継続監視 (remaining list only), C=背景資料, D=低優先
- **JST formatting**: human-readable dates without seconds/microseconds
- **V9_UI_MODE** | `simple` (explicit, maintained)

### Data preservation (read-only verified post-deploy)

| Field | Value |
|-------|-------|
| `active_context_generation` | 2 (unchanged) |
| `active_search_run_id` | `study_demo_search_20260705_145711_c06e0a1b` |
| `context_type` | `watch_profile` |
| `run_origin` | `watch_profile` |
| `source_theme_id` | `theme_6d2dfb753f7e` |
| `source_watch_profile_id` | `wp_theme_6d2dfb753f7e` |
| `source_search_plan_id` | `plan_wp_theme_6d2dfb753f7e` |
| `lineage_status` | `connected` |
| `provider_counts` | Patent 5 / Paper 5 / Web 5 |
| `tier_counts` | A 3 / B 2 / C 3 / D 7 |
| integrated signals | 15 |
| `saved_review_count` | 0 |
| `proposal_eligible` | false |

- No Theme / Watch Profile / Search Plan / Search Run artifact writes
- No Review / Proposal real data writes
- No Active Context update
- No snapshot / digest real data writes
- External API execution: **0**
- Cloud data writes: **0**

### Service configuration (unchanged)

- Service Account: `tech-cartography-v9-study-demo@devops-ai-agent-hackathon-2026.iam.gserviceaccount.com`
- Password secret: version **2**
- OpenAlex secret: version **1**
- Tavily secret: version **1**
- min instances: 0 / max instances: 1
- Public password gate: maintained
- email: false

### Production unchanged (verified post-deploy)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`, IAP enabled
- Scheduler ENABLED, `0 9 * * 1` Asia/Tokyo
- Production weekly `enabled=true`
- Production bucket, secrets, IAM, and jobs unchanged

### Unauthenticated smoke test

- HTTP 200, Streamlit SPA bootstrap detected
- No Theme/Run/Signal/Digest content or secret patterns in unauthenticated response
- Password gate maintained (login required for app content)

### Browser acceptance pending

User should confirm Top3 research value cards, Initial Baseline weekly/digest semantics, unreviewed review default, proposal insufficient message, no internal tokens, Tier labels, JST dates, and lineage/15件/Tier maintained. Validated tag not yet created.

## Final Browser Acceptance Fixes Deployment

Stage C5B-5E deploy of field-aware ranking evidence, Monitoring Profile proposal gating, and baseline saved-state UI to Study Demo only. No Theme/Profile/Plan/Run/Review/Proposal/snapshot Cloud writes during deploy. No external search or production changes.

### Deployment

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-07T15:36:00Z |
| Deployed at (JST) | 2026-07-08 00:36:00 JST |
| Expires at (UTC) | 2026-07-11T19:27:30Z |
| Expires at (JST) | 2026-07-12 04:27:30 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-utejl5os5a-uc.a.run.app |
| Revision | `tech-cartography-v9-study-demo-00022-mmv` |
| Rollback revision | `tech-cartography-v9-study-demo-00021-x27` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:5af0f4d` |
| Image digest | `sha256:234536c432bb922f6faf90aedbccad2103c088a0ea513e2071f1e16c991870a7` |
| Cloud Build ID | `a0027069-6ea7-4c62-ab4a-e30364cc3506` |
| Build source cleanup | deleted |
| Image pre-push scan | PASS |
| Git commit (code) | `5af0f4d` |
| Tag (code) | `v9-study-demo-final-acceptance-ready` |
| Tag (live candidate) | `v9-study-demo-final-acceptance-live-candidate` |

### Features deployed

- **Field-aware ranking evidence**: title/abstract verified match labels; false title match guard (3rd signal: no「タイトルにcarbon fiber」)
- **Simple internal token hidden**: `sizing:title`, `keyword_match:`, `data_basis` codes suppressed in Simple Mode ranking basis
- **Monitoring Profile proposal gating**: `evaluate_proposal_eligibility()` SSOT; insufficient review message when `proposal_eligible=false`
- **Baseline saved-state UI**: `snapshot_state=saved` hides save checkbox/button; shows「保存状態: 保存済み」
- **V9_UI_MODE** | `simple` (explicit, maintained)

### Data preservation (read-only verified post-deploy)

| Field | Value |
|-------|-------|
| `active_context_generation` | 2 (unchanged) |
| `active_search_run_id` | `study_demo_search_20260705_145711_c06e0a1b` |
| `source_theme_id` | `theme_6d2dfb753f7e` |
| `source_watch_profile_id` | `wp_theme_6d2dfb753f7e` |
| `source_search_plan_id` | `plan_wp_theme_6d2dfb753f7e` |
| `lineage_status` | `connected` |
| `provider_counts` | Patent 5 / Paper 5 / Web 5 |
| `tier_counts` | A 3 / B 2 / C 3 / D 7 |
| integrated signals | 15 |
| `saved_review_count` | 0 |
| `proposal_eligible` | false |
| `snapshot_state` | saved (`snapshot_20260705_154805_a77c05cb`) |

- No Theme / Watch Profile / Search Plan / Search Run artifact writes
- No Review / Proposal real data writes
- No snapshot real data writes
- No Active Context update
- External API execution: **0**
- Cloud data writes: **0**

### Service configuration (unchanged)

- Service Account: `tech-cartography-v9-study-demo@devops-ai-agent-hackathon-2026.iam.gserviceaccount.com`
- Password secret: version **2**
- OpenAlex secret: version **1**
- Tavily secret: version **1**
- min instances: 0 / max instances: 1
- Public password gate: maintained
- email: false

### Production unchanged (verified post-deploy)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`, IAP enabled
- Scheduler ENABLED, `0 9 * * 1` Asia/Tokyo
- Production weekly `enabled=true`
- Production bucket, secrets, IAM, and jobs unchanged

### Unauthenticated smoke test

- HTTP 200, Streamlit SPA bootstrap detected
- No Theme/Run/Signal/Digest content or secret patterns in unauthenticated response
- Password gate maintained (login required for app content)

### Browser acceptance pending

User should confirm 3rd ranking basis field accuracy, Monitoring Profile insufficient message, baseline saved UI without re-save controls, and Top3/Digest/Review/Provider/Tier regression. Validated tag not yet created.

