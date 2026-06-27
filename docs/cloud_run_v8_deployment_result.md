# Cloud Run v8 Deployment Result (Phase27O)

## Deploy summary

| Item | Value |
|------|-------|
| **Phase** | Phase27O — Cloud Run v8 Deployment |
| **Deploy date (UTC)** | 2026-06-27T01:31:20Z |
| **GCP project** | `devops-ai-agent-hackathon-2026` |
| **Region** | `us-central1` |
| **Service name** | `tech-cartography-v8-demo` |
| **Revision** | `tech-cartography-v8-demo-00001-jc7` |
| **Cloud Run URL** | https://tech-cartography-v8-demo-1020686343587.us-central1.run.app |
| **Alternate URL** | https://tech-cartography-v8-demo-utejl5os5a-uc.a.run.app |
| **Auth** | `--allow-unauthenticated`（ハッカソン提出・URL共有用） |

## Deploy command (summary)

```bash
gcloud run deploy tech-cartography-v8-demo \
  --source . \
  --region us-central1 \
  --project devops-ai-agent-hackathon-2026 \
  --allow-unauthenticated \
  --set-env-vars APP_UI_VERSION=v8,LIVE_OUTPUTS_ROOT=/tmp/tech_cartography_outputs,ENABLE_EMAIL_SEND=false,ENABLE_SCHEDULER=false,DISABLE_EMAIL_SEND=true,DISABLE_SCHEDULER=true \
  --memory 1Gi \
  --timeout 300 \
  --quiet
```

Build: Dockerfile + Cloud Build (source deploy).  
`PORT` は Cloud Run が注入。Streamlit は `${PORT:-8080}` で待受。

## Environment variables (no secrets)

| Variable | Value | Notes |
|----------|-------|-------|
| `APP_UI_VERSION` | `v8` | v8 user-flow UI |
| `LIVE_OUTPUTS_ROOT` | `/tmp/tech_cartography_outputs` | ephemeral artifact root |
| `ENABLE_EMAIL_SEND` | `false` | メール送信 OFF |
| `ENABLE_SCHEDULER` | `false` | Scheduler OFF |
| `DISABLE_EMAIL_SEND` | `true` | 二重ガード |
| `DISABLE_SCHEDULER` | `true` | 二重ガード |

**Secret / API key / SMTP password は設定していません。**  
docs および UI に secret 値は表示していません。

## Pre-deploy checks (PASS)

- `check_v8_reframe_ready.py` — PASS
- `run_v8_cloud_run_readiness_check.py` — `ready_with_warnings`, known_blockers: (none)
- `run_v8_one_case_demo_e2e_check.py` — `overall_status: demo_ready`, `manual_claim_count: 1`

## One Case demo status (Case 1)

| Metric | Value |
|--------|-------|
| `imported_count` | 1000 |
| `deduped_count` | 614 |
| `top100_count` | 100 |
| `top20_count` | 20 |
| `top5_count` | 5 |
| `manual_claim_count` | 1 |
| `claim_text_required_count` | 0 |
| `demo_readiness_status` | `demo_ready` |
| `overall_status` | `demo_ready` |
| Top5 (例) | CN108286090A, CN117987966A, CN105401262A, CN105506785B, CN109402791B |
| Manual claim | CN108286090A — `manual_input`（`claims_input.csv` に同梱） |

## Docker image contents policy

`.dockerignore` により除外:

- `.git`, `.env`, `outputs/`, `__pycache__`, `*.db`, credentials
- `cases/*/source_candidates_large.csv`, `cases/*/source_candidates_large_deduped.csv`

同梱（デモ用）:

- `cases/case_01_pan_graphitization/large_candidates/case_01_bigquery_export_1000.csv`
- `cases/case_01_pan_graphitization/claims_input.csv`（manual claim 含む）
- `cases/*/case_profile.yaml`, `source_candidates.csv` 等

個人情報・secret は cases CSV / claims に含めていません。

## Post-deploy verification

| Check | Result |
|-------|--------|
| `/_stcore/health` | HTTP 200 |
| Streamlit 起動 | OK（ページタイトル Streamlit） |
| v8 UI | `APP_UI_VERSION=v8` 設定済み |
| メール送信 | **実行していない** |
| Scheduler 起動 | **実行していない** |
| 外部 API / BigQuery / LLM | **実行していない** |

### ブラウザ確認（推奨タブ）

1. はじめに — v8 demo / Cloud Run 注意表示
2. Sources一覧 — Case 1 選択
3. 読むべき特許 — Top5 表示（再生成は `/tmp` に出力）
4. Claim Map — CN108286090A `manual_input`
5. Evidence Map / Gap / Next Actions / 定点観測 / Export — クラッシュしないこと

**注意:** Cloud Run 上の artifact（Top5 pack 等）は **ephemeral**。再起動後は UI から再生成が必要。`claims_input.csv` と large CSV は image 同梱のため Claim Map の manual claim は表示可能。

## Remaining caveats

- `LIVE_OUTPUTS_ROOT=/tmp` — 生成 artifact は再起動で消失
- Cloud Run 初回アクセスはコールドスタートで数十秒かかる場合あり
- Evidence / Gap count=0 は artifact 未生成または true zero — Export タブで区別表示
- `--allow-unauthenticated` — 提出後に IAM で制限可能
- Phase27N で未実施だった Cloud Build / deploy を **本 Phase で初回実行**

## Next phase

**Phase27P** — 提出用 README / スクショ / 動画準備

- Cloud Run URL を README に記載
- 主要タブのスクショ（Case 1, Top5, manual claim, Export）
- デモ台本（メール・Scheduler・外部 API なし）

## Safety confirmations

- [x] No email send
- [x] No scheduler start
- [x] No secret exposed in docs or env
- [x] No claim auto-generation
- [x] No Watch Profile auto-update
