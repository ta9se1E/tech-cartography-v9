# Phase 25O — Cloud Run IAP Cutover Runbook and Safety Checks

## Phase 25N との差分

| Phase | 内容 |
|-------|------|
| 25N | アプリ側 IAP-ready Auth Bridge（`AUTH_PROVIDER_MODE`, IAP Identity Adapter, JWT 受け皿） |
| **25O** | **GCP 側 IAP 切替の Runbook、preflight スクリプト、ロールバック手順、Cutover Status UI** |

Phase25N は「アプリが IAP identity を受け取れる」状態を作りました。Phase25O は「人間が安全に GCP IAP を ON にする手順」と確認ツールを提供します。**コードやスクリプトから自動的に IAP を ON/OFF にしません。**

## 目的

Basic Login 中心の運用から、Google IAP 中心の運用へ段階的に切り替えるための準備です。

## いきなり本番切替しない理由

- IAP 有効化とアプリ `AUTH_PROVIDER_MODE` の不整合で全員ロックアウトするリスクがある
- role mapping（`TECH_CARTOGRAPHY_ADMIN_EMAILS` 等）未設定で IAP ユーザーを拒否するリスクがある
- Direct Cloud Run URL を IAP なしで開放したままヘッダーを信頼するとなりすまし可能
- ロールバック手順を事前に用意しないと障害時の復旧が遅れる

## 推奨切替モード（段階的）

1. **`AUTH_PROVIDER_MODE=hybrid`** で再デプロイ（Basic fallback 維持）
2. **Cloud Run IAP を有効化**（手動。下記コマンド参照）
3. **Google ログインで入れること**を確認
4. **Run History** に `auth_provider=google_iap` が記録されることを確認
5. 問題なければ **`AUTH_PROVIDER_MODE=iap`** へ切替（Basic fallback を外す判断は別途）

## 事前確認

ローカルまたは CI で以下を実行してください。

```bash
conda run -n 2026hack python scripts/check_iap_cutover_ready.py \
  --project devops-ai-agent-hackathon-2026 \
  --region us-central1 \
  --service tech-cartography-v7-live
```

確認項目の概要:

- gcloud project / project number / target service / region
- Cloud Run 環境変数（`AUTH_PROVIDER_MODE`, role mapping, `LIVE_OUTPUTS_ROOT` 等）
- Cloud Storage mount の有無
- Secret Manager 参照（値は表示しない）
- Run History ディレクトリ
- IAP API 有効化状態
- IAP service agent 想定名
- 現在 IAP が有効か（describe から読み取り可能な場合）

## 前提変数

```bash
PROJECT_ID=devops-ai-agent-hackathon-2026
REGION=us-central1
SERVICE=tech-cartography-v7-live
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
IAP_SA="service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com"
```

## GCP コマンド（手動実行のみ）

> **注意:** 以下は Runbook 用のコマンド例です。`check_iap_cutover_ready.py` やアプリコードからは実行しません。

### IAP API 有効化

```bash
gcloud services enable iap.googleapis.com --project="$PROJECT_ID"
```

### IAP service agent 作成

```bash
gcloud beta services identity create \
  --service=iap.googleapis.com \
  --project="$PROJECT_ID"
```

### Phase25N hybrid mode で再デプロイ

```bash
echo "Set fallback admin login password, then press Enter:"
read -s TC_LOGIN_PASSWORD
echo

gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --update-env-vars REQUIRE_LOGIN=true,APP_DEFAULT_MODE=analyst,AUTH_PROVIDER_MODE=hybrid,IAP_JWT_VERIFY_MODE=off,SHOW_DEVELOPER_MODE=false,DEMO_OUTPUTS_ROOT=demo_outputs,LIVE_OUTPUTS_ROOT=/mnt/live_artifacts/outputs,DISABLE_EXTERNAL_API=true,DISABLE_EMAIL_SEND=true,DISABLE_SCHEDULER=true,TECH_CARTOGRAPHY_LOGIN_USERNAME=admin,TECH_CARTOGRAPHY_LOGIN_PASSWORD="$TC_LOGIN_PASSWORD",TECH_CARTOGRAPHY_ADMIN_EMAILS='your-email@example.com',TECH_CARTOGRAPHY_ALLOWED_EMAIL_DOMAINS='example.com' \
  --update-secrets TAVILY_API_KEY=tech-cartography-tavily-api-key:latest,SMTP_PASSWORD=tech-cartography-smtp-password:latest

unset TC_LOGIN_PASSWORD
```

### IAP を有効化（候補）

```bash
gcloud run services update "$SERVICE" \
  --region "$REGION" \
  --iap
```

### IAP service agent へ Cloud Run Invoker 付与

```bash
gcloud run services add-iam-policy-binding "$SERVICE" \
  --region "$REGION" \
  --member="serviceAccount:${IAP_SA}" \
  --role=roles/run.invoker
```

### IAP access 付与

```bash
gcloud iap web add-iam-policy-binding \
  --member="user:your-email@example.com" \
  --role=roles/iap.httpsResourceAccessor \
  --region="$REGION" \
  --resource-type=cloud-run \
  --service="$SERVICE"
```

### IAP policy 確認

```bash
gcloud iap web get-iam-policy \
  --region="$REGION" \
  --resource-type=cloud-run \
  --service="$SERVICE"
```

### Cloud Run IAP 有効確認

```bash
gcloud run services describe "$SERVICE" \
  --region "$REGION"
```

期待: `Iap Enabled: true` 相当の表示、または IAP 有効状態が確認できること。

## 手動確認手順

1. IAP 経由 URL でアプリにアクセスし、Google アカウントでログインできる
2. 設定タブの **Authentication Status** / **IAP Cutover Status** で `auth_provider=google_iap` を確認
3. 手動実行後、Run History に `auth_provider=google_iap` が記録される
4. hybrid 期間中、IAP なし Direct URL から Basic Login fallback が動作する（移行期間のみ）
5. `DISABLE_EXTERNAL_API=true` / `DISABLE_EMAIL_SEND=true` / `DISABLE_SCHEDULER=true` が維持されている

## ロールバック手順

障害時は以下の順で戻します。**手動実行のみ。**

### IAP を OFF に戻す

```bash
gcloud run services update "$SERVICE" \
  --region "$REGION" \
  --no-iap
```

### Basic fallback へ戻す

```bash
echo "Set fallback admin login password, then press Enter:"
read -s TC_LOGIN_PASSWORD
echo

gcloud run services update "$SERVICE" \
  --region "$REGION" \
  --update-env-vars AUTH_PROVIDER_MODE=basic,REQUIRE_LOGIN=true,TECH_CARTOGRAPHY_LOGIN_USERNAME=admin,TECH_CARTOGRAPHY_LOGIN_PASSWORD="$TC_LOGIN_PASSWORD",DISABLE_EXTERNAL_API=true,DISABLE_EMAIL_SEND=true,DISABLE_SCHEDULER=true

unset TC_LOGIN_PASSWORD
```

### ロールバック後の確認

- Basic Login で入れる
- Run History が残る（`LIVE_OUTPUTS_ROOT` 配下）
- `LIVE_OUTPUTS_ROOT` が維持されている
- Cloud Storage mount が維持されている

## Known risks

| リスク | 対策 |
|--------|------|
| role mapping 未設定で IAP ユーザー拒否 | 事前に `TECH_CARTOGRAPHY_ADMIN_EMAILS` / `ALLOWED_EMAIL_DOMAINS` を設定 |
| IAP ON のみでアプリが basic のまま | hybrid → iap の順で段階切替 |
| Direct URL 開放 + ヘッダー信頼 | IAP 有効後は Direct URL を信頼しない。JWT strict を検討 |
| IAP service agent に invoker 未付与 | preflight で IAP_SA を表示し、手順で付与 |
| パスワードをシェル履歴に残す | `read -s` + `unset` を使用 |

## Organization なし / 外部ユーザー利用時の注意

- Google Workspace organization がない場合、IAP のユーザー管理は Google アカウント単位になる
- 外部ユーザーには `roles/iap.httpsResourceAccessor` を個別付与するか、許可ドメインで role mapping する
- `TECH_CARTOGRAPHY_ALLOWED_EMAIL_DOMAINS` は慎重に設定（広すぎるドメインは避ける）

## 既存 Basic Login fallback をいつ消すか

- hybrid で IAP ログイン・Run History・主要機能が **1〜2 週間** 問題なく動作した後
- 全運用メンバーが IAP アクセス権を持っていることを確認後
- `AUTH_PROVIDER_MODE=iap` へ切替し、Basic パスワード env を削除するかダミー化（別 Phase で検討）

## Direct Cloud Run URL を IAP なしで開放しない方針

- 本番では IAP 有効化後、**IAP 経由のアクセスのみ**を正規ルートとする
- `--allow-unauthenticated` は Cloud Run Invoker を IAP SA に限定する構成とセットで理解する
- `IAP_JWT_VERIFY_MODE=strict` + `IAP_EXPECTED_AUDIENCE` は本番切替後に検討

## secret / JWT / password 非保存方針

- Runbook・preflight・UI に password / JWT 全文 / API キー値を含めない
- Run History にも保存しない（Phase25N 準拠）
- デプロイ時パスワードは `read -s` で入力し、シェル変数は `unset` する

## 次 Phase 候補

- Phase25P: CI/CD
- Phase25Q: 承認付きメンバー送信
- Phase25R: scheduler
