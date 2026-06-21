# Phase 25H — Live Artifact Persistence with Cloud Storage Mount

## 目的

Phase 25E〜25G で Cloud Run live 上の以下の流れが動作するようになりました。

- Tavily Web 検索
- Web Signal Pack 作成
- Digest Mail Preview 作成
- Self-only Email Send Test

これまで成果物は Cloud Run コンテナ内の `outputs/` に保存されていました。Revision 更新やインスタンス切替でファイルが消える可能性があるため、live 成果物を Cloud Storage へ永続保存できるようにします。

**この Phase では新しい AI 機能は追加しません。** メール送信範囲も広げず、scheduler も ON にしません。

## なぜ Cloud Run 内 `outputs/` だけでは不十分か

Cloud Run のコンテナファイルシステムは **エフェメラル（一時的）** です。

- 新 Revision へのデプロイでコンテナが差し替わる
- スケールダウンでインスタンスが破棄される
- 複数インスタンス間でファイルが共有されない

職場向けサービスとして live 成果物（Web Signal / Digest Preview / Email Send Log）を残すには、コンテナ外の永続ストレージが必要です。

## 環境変数 `LIVE_OUTPUTS_ROOT`

| 状態 | 保存ルート |
|------|-----------|
| 未設定 | 既存どおり `{project_root}/outputs/` |
| 設定あり | `LIVE_OUTPUTS_ROOT` 配下 |

例: `LIVE_OUTPUTS_ROOT=/mnt/live_artifacts/outputs`

| 成果物 | 保存先 |
|--------|--------|
| Web Signal Pack | `/mnt/live_artifacts/outputs/live_web_signals/` |
| Digest Preview | `/mnt/live_artifacts/outputs/live_digest_preview/` |
| Email Send Log | `/mnt/live_artifacts/outputs/live_email_send/` |

## Cloud Storage bucket 作成

プロジェクト内で **一意の bucket 名** を選びます（例: `tech-cartography-v7-live-artifacts-<PROJECT_ID>`）。

```bash
export PROJECT_ID="$(gcloud config get-value project)"
export BUCKET_NAME="tech-cartography-v7-live-artifacts-${PROJECT_ID}"

gcloud storage buckets create "gs://${BUCKET_NAME}" \
  --location=us-central1 \
  --uniform-bucket-level-access
```

## Cloud Run service account へ Storage Object User

live サービスが使用する service account（デフォルトまたは専用 SA）に、bucket への読み書き権限を付与します。

```bash
export SA="$(gcloud run services describe tech-cartography-v7-live \
  --region us-central1 \
  --format='value(spec.template.spec.serviceAccountName)')"

gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
  --member="serviceAccount:${SA}" \
  --role="roles/storage.objectUser"
```

## Cloud Run に volume mount を設定

```bash
gcloud run services update tech-cartography-v7-live \
  --region us-central1 \
  --add-volume name=live-artifacts,type=cloud-storage,bucket="${BUCKET_NAME}" \
  --add-volume-mount volume=live-artifacts,mount-path=/mnt/live_artifacts \
  --update-env-vars LIVE_OUTPUTS_ROOT=/mnt/live_artifacts/outputs
```

mount 先 `/mnt/live_artifacts` に bucket 全体がマウントされます。`LIVE_OUTPUTS_ROOT` で `outputs` サブディレクトリを指定し、他用途との名前空間を分けます。

## demo service は変更しない

- **demo service**（`tech-cartography-v7-demo` 等）: 従来どおり `DEMO_OUTPUTS_ROOT` / ローカル demo 出力。`LIVE_OUTPUTS_ROOT` は設定しない。
- **live service**（`tech-cartography-v7-live`）のみ永続化を有効化。

## 実装モジュール

- `src/tech_cartography/runtime/live_artifact_paths.py` — パス解決・writable チェック
- `src/tech_cartography/ui/live_artifact_storage_ui.py` — 管理者向け保存先状態 UI

## UI 表示

設定タブおよび analyst「入力・実行」タブの admin expander:

**Live Artifact Storage（管理者向け）**

- `LIVE_OUTPUTS_ROOT`（未設定時は fallback 表示）
- active storage root
- 各 artifact ディレクトリ
- writable チェック
- latest artifact counts

Secret 値（API キー、`SMTP_PASSWORD` 等）は表示しません。

## ローカル確認

通常 fallback:

```bash
REQUIRE_LOGIN=true \
APP_DEFAULT_MODE=analyst \
TECH_CARTOGRAPHY_LOGIN_USERNAME=admin \
TECH_CARTOGRAPHY_LOGIN_PASSWORD='test-password' \
DISABLE_EXTERNAL_API=true \
DISABLE_EMAIL_SEND=true \
DISABLE_SCHEDULER=true \
streamlit run app.py
```

任意 root:

```bash
REQUIRE_LOGIN=true \
APP_DEFAULT_MODE=analyst \
TECH_CARTOGRAPHY_LOGIN_USERNAME=admin \
TECH_CARTOGRAPHY_LOGIN_PASSWORD='test-password' \
LIVE_OUTPUTS_ROOT=/tmp/tech_cartography_live_outputs \
DISABLE_EXTERNAL_API=true \
DISABLE_EMAIL_SEND=true \
DISABLE_SCHEDULER=true \
streamlit run app.py
```

## 次 Phase

Phase 25H 完了後、**Watch Expansion Proposal** へ進む方針です。
