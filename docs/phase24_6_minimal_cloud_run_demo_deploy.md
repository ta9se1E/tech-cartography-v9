# Phase 24.6 — Minimal Cloud Run Demo Deploy

## 目的

Cloud Run URL で Tech Cartography v7 の **「デモを見る」** モードを開ける最小構成を用意する。  
UI 再設計・分析ロジック変更・外部 API 自動実行は行わない。

## デプロイ構成

| ファイル | 役割 |
|---------|------|
| `Procfile` | Streamlit を `0.0.0.0:${PORT}` で起動 |
| `runtime.txt` | Python 3.11（Cloud Run buildpacks） |
| `.gcloudignore` | ソースアップロード時に secrets / 大量 outputs を除外し、US デモ bundle のみ同梱 |
| `.dockerignore` | Docker ビルド時も同様 |
| `.env.example` | Cloud Run 用環境変数のテンプレ（**PORT は書かない**） |

## Cloud Run 用環境変数

| 変数 | 推奨値 | 説明 |
|------|--------|------|
| `SHOW_DEVELOPER_MODE` | `false` | 開発者向けモード非表示 |
| `APP_DEFAULT_MODE` | `demo` | 初期 UI を「デモを見る」に |
| `DISABLE_EXTERNAL_API` | `true` | OpenAlex/Tavily/BigQuery UI 実行を無効 |
| `DISABLE_EMAIL_SEND` | `true` | SMTP 送信を無効 |
| `DISABLE_SCHEDULER` | `true` | scheduler / launchd / cron 表示を無効 |
| `STREAMLIT_SERVER_HEADLESS` | `true` | ヘッドレス実行（ローカル参考用） |

**注意:** `PORT` は Cloud Run が注入するため `--set-env-vars` や `.env.example` に固定値を書かない。

## demo outputs の扱い

`outputs/` は `.gitignore` 対象だが、Cloud Run `--source .` アップロードでは `.gcloudignore` で **US-12565719-B2 デモ bundle のみ** を同梱する:

- `outputs/evidence_map_synthesis/US-12565719-B2/**`
- `outputs/openalex_limited_execution/**`
- `outputs/strategic_watch_briefs/US-12565719-B2/**`
- `outputs/web_signals/tavily_pan_carbon_fiber/**`
- `outputs/validation/final_validation/**`
- `outputs/delivery/*US-12565719-B2*` 等

デプロイ前に `python scripts/check_cloudrun_demo_ready.py` で存在確認する。

## デプロイ例

```bash
gcloud config set project devops-ai-agent-hackathon-2026

gcloud run deploy tech-cartography-v7-demo \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars SHOW_DEVELOPER_MODE=false,APP_DEFAULT_MODE=demo,DISABLE_EXTERNAL_API=true,DISABLE_EMAIL_SEND=true,DISABLE_SCHEDULER=true
```

## ローカル Cloud Run 相当確認

```bash
PORT=8080 \
SHOW_DEVELOPER_MODE=false \
APP_DEFAULT_MODE=demo \
DISABLE_EXTERNAL_API=true \
DISABLE_EMAIL_SEND=true \
DISABLE_SCHEDULER=true \
streamlit run app.py \
  --server.address=0.0.0.0 \
  --server.port=8080 \
  --server.headless=true \
  --server.fileWatcherType=none \
  --browser.gatherUsageStats=false
```

`http://localhost:8080` でデモモード・開発者向け非表示・US デモ成果物表示を確認する。

## 安全方針

- 外部 API は UI から自動実行しない（`DISABLE_EXTERNAL_API=true`）
- メール送信しない（`DISABLE_EMAIL_SEND=true`）
- scheduler / launchd / cron は Cloud Run 提出用では非表示
- 通常画面に `/Users/` ローカルパスを出さない（Phase 24.5 済み）

## 前フェーズ

Phase 24.5A〜F で Demo UI 安全化・ノイズ削減済み。本 Phase はデプロイ最小差分のみ。
