# Cloud Run v8 反映準備 (Phase27N)

## この Phase の位置づけ

**Phase27N は Cloud Run deploy ではありません。** Cloud Build / `gcloud run deploy` / 外部 API / メール送信 / Scheduler 起動は **この Phase では実行しません**。

目的:

- v8 Streamlit app が Cloud Run 上で起動できる構成か **ローカルで点検**
- 環境変数・Secret 方針・artifact 出力方針を整理
- deploy 前チェックリスト / 提出デモ準備チェックリストを生成
- **Phase27O** で実際に deploy する

## v8 起動コマンド

### ローカル

```bash
conda run -n 2026hack streamlit run app.py
# または 8502 等 — ローカルは PORT 固定でも可
```

### Cloud Run 推奨（Phase27O で使用 — **この Phase では実行しない**）

```bash
streamlit run app.py \
  --server.port=${PORT:-8080} \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --server.fileWatcherType=none \
  --browser.gatherUsageStats=false
```

`Procfile` と `Dockerfile` に同等の設定があります。

## app.py / v8 entrypoint

- `APP_UI_VERSION` 未設定時 **default = v8**
- `APP_UI_VERSION=v7` で v7 UI に fallback（削除していない）
- エントリ: `app.py` → `render_v8_user_flow_app`

## 必要環境変数（Secret 値は docs に書かない）

| 変数 | Cloud Run 推奨 | 説明 |
|------|----------------|------|
| `PORT` | Cloud Run 注入 | 固定値を docs / `.env.example` に書かない |
| `APP_UI_VERSION` | `v8` | v8 user-flow UI |
| `LIVE_OUTPUTS_ROOT` | `/tmp/tech_cartography_outputs` | artifact 一時出力 |
| `DISABLE_EMAIL_SEND` | `true` | メール送信 OFF（機能は保持） |
| `DISABLE_SCHEDULER` | `true` | Scheduler OFF（機能は保持） |
| `DISABLE_EXTERNAL_API` | `true` | 外部 API デフォルト OFF（推奨） |

### Secret Manager に入れるもの（placeholder のみ — **値を docs に書かない**）

- `SMTP_PASSWORD` / `TC_SMTP_PASSWORD`
- `TAVILY_API_KEY`
- GCP service account JSON（必要な場合）

`.env` は git / Docker image に含めません。

## OUTPUT_ROOT / artifact 出力方針

| 環境 | 出力ルート | 永続性 |
|------|-----------|--------|
| ローカル開発 | `outputs/local_*` | ローカルディスク |
| Cloud Run 一時 | `/tmp/tech_cartography_outputs` (`LIVE_OUTPUTS_ROOT`) | **ephemeral** — 再起動で消える |
| 将来 (Phase27O+) | Cloud Storage | 永続化検討 |

**注意:** Cloud Run のファイルシステムは永続保存前提にしない。生成 Pack は **ダウンロード** 前提。Cloud Storage 実装は Phase27O 以降。

`OUTPUT_ROOT` 統一変数は Phase27O 以降で `LIVE_OUTPUTS_ROOT` と整理予定。

## メール送信 / Scheduler

- **必須機能として削除しない**
- Cloud Run 上では **デフォルト OFF**: `DISABLE_EMAIL_SEND=true`, `DISABLE_SCHEDULER=true`
- 定点観測タブでは計画・プレビューのみ — 本 Phase では実行しない

## Demo data 準備（Phase27N.5）

Cloud Run 前に **Case 1** だけ実在 CSV で E2E を通してください。

```bash
conda run -n 2026hack python scripts/run_v8_one_case_demo_e2e_check.py
```

詳細: `docs/one_case_real_demo_runbook.md`

## Demo data 準備

Phase27M Demo Readiness が `not_ready`（Large Candidate CSV 未投入等）でも **Cloud deploy の技術ブロッカーではありません**。
ただし **提出デモのブロッカー** として扱います。

提出前チェック:

1. 少なくとも **1ケース** で実データ CSV (`source_candidates_large.csv`) を投入
2. Top100 / Top20 / Top5 を生成
3. claim 本文を **1件** 手動投入（望ましい）
4. Evidence Map / Gap / Demo Polish Pack / Demo Readiness Pack を生成
5. Export タブから Pack をダウンロード確認

## Deploy 前チェックリスト

1. `python scripts/run_v8_cloud_run_readiness_check.py` — Cloud Run Readiness Pack 生成
2. `overall_status` / `known_blockers` を確認
3. `demo_data_checklist.md` — 提出デモ不足を解消
4. `env_var_template.md` — Secret 値を手動で docs に書いていないか確認
5. `artifact_policy.md` — ephemeral FS を理解
6. **Phase27O** まで Cloud Build / deploy を実行しない

## Phase27O で実行予定（参考 — **この Phase では実行しない**）

```bash
# 実行しない — Phase27O まで保留
# gcloud builds submit --tag REGION-docker.pkg.dev/PROJECT/REPO/patentscout-v8
# gcloud run deploy patentscout-v8 \
#   --image REGION-docker.pkg.dev/PROJECT/REPO/patentscout-v8 \
#   --region asia-northeast1 \
#   --set-env-vars APP_UI_VERSION=v8,DISABLE_EMAIL_SEND=true,DISABLE_SCHEDULER=true,\
# LIVE_OUTPUTS_ROOT=/tmp/tech_cartography_outputs
```

## Cloud Run Readiness Pack

Export タブまたは:

```bash
conda run -n 2026hack python scripts/run_v8_cloud_run_readiness_check.py
```

出力: `outputs/local_v8_cloud_run_readiness/readiness_*/`

- `cloud_run_readiness_report.json` / `.md`
- `deploy_preparation_checklist.md`
- `demo_data_checklist.md`
- `operator_checklist.md`
- `env_var_template.md`
- `artifact_policy.md`
- `cloud_run_readiness_manifest.json`

## 安全上の注意

- FTO / 侵害 / 有効性判断は行いません
- Evidence Map is not proof
- Gap is not invalidity
- Secret 値を export / UI / docs に含めません

## 次 Phase

- **Phase27O** — Cloud Run v8 反映
- **Phase27P** — 提出用 README / スクショ / 動画準備
