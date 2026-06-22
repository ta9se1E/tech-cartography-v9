# Phase 25P — CI/CD Deploy Pipeline and Safe Cloud Run Release

## Phase 25O との差分

| Phase | 内容 |
|-------|------|
| 25O | IAP Cutover Runbook、preflight、手動 gcloud 手順 |
| **25P** | **Cloud Build CI/CD、`deploy_live_safe.sh`、rollback script、CI チェック** |

Phase25O までで IAP + Google ログイン + Run History が live で動作しています。Phase25P は **手動 `gcloud run deploy --source .` への依存を減らし**、テスト・チェック付きの安全なデプロイパイプラインを整備します。

## なぜ CI/CD が必要か

手動デプロイで起きやすい事故:

- テスト未実行のまま本番反映
- 必須 env（`DISABLE_SCHEDULER` 等）の付け忘れ
- IAP を意図せず無効化（`--no-iap`）
- Secret 値をコマンドラインや YAML に直書き
- Cloud Storage mount の脱落による Run History 消失

## cloudbuild.yaml の役割

`cloudbuild.yaml` は **2ステップ** で構成されます。

| Step | イメージ | 役割 |
|------|---------|------|
| **#0 quality-gate** | `python:3.11-slim` | 依存 install、`compileall` / `pytest` / check scripts |
| **#1 iap-preflight-and-deploy** | `cloud-sdk:slim` | **gcloud のみ** — bucket/service preflight + Cloud Run deploy |

Step #0 で以下を実行します。

1. ignore ファイル復元 / `pip install` / `compileall` / `pytest` / check scripts

Step #1 では **pip install を実行しません**（PEP 668 / externally-managed-environment 回避）。

1. `gcloud config set project`
2. `gcloud storage buckets describe`（live artifacts bucket）
3. `gcloud run services describe`（preflight）
4. `gcloud run deploy`（IAP 維持、`--no-iap` なし）
5. deploy 後 `gcloud run services describe`（URL / revision / volume mount 確認）

### externally-managed-environment の回避方針

`gcr.io/google.com/cloudsdktool/cloud-sdk:slim` の Python は **システム管理環境** です。
Step #1 で `pip install` すると `externally-managed-environment` エラーになります。

- Python チェックは Step #0 に集約
- Step #1 は gcloud / bash のみ
- `--break-system-packages` は使わない

### IAM 不足と pip 環境エラーの見分け方

| 症状 | 典型原因 |
|------|----------|
| `externally-managed-environment` | cloud-sdk イメージでの `pip install`（IAM ではない） |
| `Permission denied` / `403` on `gcloud run deploy` | Cloud Build SA の IAM 不足 |
| `Secret ... not found` | Secret Manager 参照または accessor ロール不足 |

**Secret 値は YAML に直書きしません。** Secret Manager 参照のみです。

### 手動 Cloud Build 実行例

```bash
gcloud builds submit \
  --project devops-ai-agent-hackathon-2026 \
  --config cloudbuild.yaml \
  --substitutions=_REGION=us-central1,_SERVICE=tech-cartography-v7-live,_LIVE_ARTIFACTS_BUCKET=tech-cartography-v7-live-artifacts-1020686343587
```

## deploy_live_safe.sh の使い方

ローカルから安全に live へデプロイする場合:

```bash
chmod +x scripts/deploy_live_safe.sh
./scripts/deploy_live_safe.sh
```

環境変数で上書き可能:

```bash
PROJECT_ID=devops-ai-agent-hackathon-2026 \
REGION=us-central1 \
SERVICE=tech-cartography-v7-live \
LIVE_ARTIFACTS_BUCKET=tech-cartography-v7-live-artifacts-1020686343587 \
./scripts/deploy_live_safe.sh
```

実行内容:

1. compileall / pytest / 全 check scripts
2. Cloud Run deploy（**IAP は維持 — `--no-iap` なし**）
3. service describe で URL / revision 確認

### deploy 時の env（IAP mode）

| 変数 | 値 |
|------|-----|
| `AUTH_PROVIDER_MODE` | `iap` |
| `TECH_CARTOGRAPHY_ADMIN_EMAILS` | `ta9se1@gmail.com` |
| `LIVE_OUTPUTS_ROOT` | `/mnt/live_artifacts/outputs` |
| `DISABLE_EXTERNAL_API` | `true` |
| `DISABLE_EMAIL_SEND` | `true` |
| `DISABLE_SCHEDULER` | `true` |

`TECH_CARTOGRAPHY_LOGIN_PASSWORD` は IAP mode では原則不要です。

## rollback_live_to_basic.sh の使い方

IAP や deploy 後に入れなくなった場合の緊急復旧:

```bash
chmod +x scripts/rollback_live_to_basic.sh
./scripts/rollback_live_to_basic.sh
```

- `--no-iap` で IAP を OFF
- `AUTH_PROVIDER_MODE=basic` + admin パスワード（`read -s` 入力）
- `LIVE_OUTPUTS_ROOT` と Cloud Storage mount を維持

## GitHub 連携手順

1. リポジトリを GitHub に push
2. GCP Console → Cloud Build → Repositories で GitHub 接続
3. 対象リポジトリをリンク

## Cloud Build trigger 作成手順

```bash
gcloud builds triggers create github \
  --project=devops-ai-agent-hackathon-2026 \
  --name=tech-cartography-v7-live-deploy \
  --repo-name=PatentScout_AI_v7 \
  --repo-owner=<GITHUB_OWNER> \
  --branch-pattern="^checkpoint/before-cloud-run$" \
  --build-config=cloudbuild.yaml \
  --substitutions=_REGION=us-central1,_SERVICE=tech-cartography-v7-live,_LIVE_ARTIFACTS_BUCKET=tech-cartography-v7-live-artifacts-1020686343587
```

> ブランチ名は運用ブランチに合わせて変更してください。初回は **手動 `gcloud builds submit`** で検証を推奨します。

## 必要な IAM

Cloud Build サービスアカウント（`<PROJECT_NUMBER>@cloudbuild.gserviceaccount.com`）に例:

| ロール | 用途 |
|--------|------|
| `roles/run.admin` | Cloud Run deploy |
| `roles/iam.serviceAccountUser` | Run SA の actAs |
| `roles/secretmanager.secretAccessor` | Secret 参照 |
| `roles/storage.admin` または objectUser | build source / artifacts |

Cloud Run 実行 SA には Storage Object User（live artifacts bucket）が必要です（Phase25H 参照）。

## 必要な Secret Manager 参照

| Env | Secret |
|-----|--------|
| `TAVILY_API_KEY` | `tech-cartography-tavily-api-key:latest` |
| `SMTP_PASSWORD` | `tech-cartography-smtp-password:latest` |

値はリポジトリ・ログ・UI に保存しません。

## IAP を ON のまま維持する方針

- `deploy_live_safe.sh` / `cloudbuild.yaml` は **`--no-iap` を含めない**
- `AUTH_PROVIDER_MODE=iap` を deploy env に含める
- IAP 無効化は `rollback_live_to_basic.sh` のみ（手動・緊急時）

## env / secrets / mount の管理方針

| 種別 | 管理場所 |
|------|----------|
| 非機密 env | `cloudbuild.yaml` / deploy script の `--update-env-vars` |
| API / SMTP | Secret Manager + `--update-secrets` |
| ログインパスワード | IAP 運用時は未使用。rollback 時のみ `read -s` |
| live artifacts | Cloud Storage bucket + volume mount `/mnt/live_artifacts` |

## 本番前の注意

- 初回は `gcloud builds submit` で手動実行し、全ステップ PASS を確認
- deploy 後に Google ログイン・Run History・Authentication Status を確認
- Direct Cloud Run URL を IAP なしで信頼しない
- scheduler / 一斉メール / 外部 API 自動実行はこの Phase では ON にしない

## check_cicd_ready.py

```bash
conda run -n 2026hack python scripts/check_cicd_ready.py \
  --project devops-ai-agent-hackathon-2026 \
  --region us-central1 \
  --service tech-cartography-v7-live
```

CI 用: `--skip-gcloud` で artifact のみ検証可能。

## 次 Phase 候補

- 承認付きメンバー送信
- scheduler
- Gemini による提案品質向上
