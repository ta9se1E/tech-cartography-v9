# Phase 24.6 — Minimal Cloud Run Demo Deploy

## 目的

Cloud Run URL で Tech Cartography v7 の **「デモを見る」** モードを開ける最小構成を用意する。  
UI 再設計・分析ロジック変更・外部 API 自動実行は行わない。

## デプロイ構成

| ファイル | 役割 |
|---------|------|
| `Procfile` | Streamlit を `0.0.0.0:${PORT}` で起動 |
| `runtime.txt` | Python 3.11（Cloud Run buildpacks） |
| `.gcloudignore` | secrets / ローカル `outputs/` を除外。**`demo_outputs/` は同梱** |
| `.dockerignore` | Docker ビルド時も同様 |
| `demo_outputs/US-12565719-B2/` | Cloud Run 提出用デモ成果物バンドル（git 追跡） |
| `scripts/bundle_demo_outputs.py` | ローカル `outputs/` から bundle を再生成 |
| `.env.example` | Cloud Run 用環境変数のテンプレ（**PORT は書かない**） |

## Phase 24.6A — Evidence Map missing の原因と対処

### 原因

Cloud Run コンテナ内にはローカルの `outputs/` は存在しません。  
Phase 24.6 当初の `.gcloudignore` では `outputs/**` を除外し `!outputs/...` で再包含しようとしましたが、**gcloud の upload 対象に demo 成果物が入らない** 状態でした。

```bash
gcloud meta list-files-for-upload | grep -E "US-12565719|evidence_map"
# → demo_outputs も outputs も含まれない
```

その結果 Cloud Run 上で `Evidence Map missing` が表示されました。

### 対処（24.6A）

1. **`demo_outputs/US-12565719-B2/`** に必要最小ファイルをコピー（git 追跡）
2. `.gcloudignore` で `outputs/` のみ除外し、**`demo_outputs/` は除外しない**
3. Cloud Run 環境変数 **`DEMO_OUTPUTS_ROOT=demo_outputs`** でアプリが bundle を優先読込
4. デプロイ前に upload 対象を確認:

```bash
gcloud meta list-files-for-upload | grep -E "demo_outputs|US-12565719|evidence_map|selected_evidence|claim_paper|openalex"
python scripts/check_cloudrun_demo_ready.py
```

## Cloud Run 用環境変数

| 変数 | 推奨値 | 説明 |
|------|--------|------|
| `SHOW_DEVELOPER_MODE` | `false` | 開発者向けモード非表示 |
| `APP_DEFAULT_MODE` | `demo` | 初期 UI を「デモを見る」に |
| `DEMO_OUTPUTS_ROOT` | `demo_outputs` | 提出用デモ bundle のルート |
| `DISABLE_EXTERNAL_API` | `true` | OpenAlex/Tavily/BigQuery UI 実行を無効 |
| `DISABLE_EMAIL_SEND` | `true` | SMTP 送信を無効 |
| `DISABLE_SCHEDULER` | `true` | scheduler / launchd / cron 表示を無効 |
| `STREAMLIT_SERVER_HEADLESS` | `true` | ヘッドレス実行（ローカル参考用） |

**注意:** `PORT` は Cloud Run が注入するため `--set-env-vars` や `.env.example` に固定値を書かない。

## demo_outputs バンドル

`python scripts/bundle_demo_outputs.py` でローカル `outputs/` から再生成。

必須ファイル例:

- `evidence_map_synthesis.md` / `.json` / `evidence_map_items.csv`
- `selected_evidence_papers.csv` / `claim_paper_candidate_links.csv`
- `paper_candidate_relevance_report.md` / `openalex_execution_summary.md`
- `web_signal_review_pack.json` ほか Review Pack 関連
- `strategic_watch_brief.md` / `top_strategic_watch_items.csv`
- `weekly_digest_preview_US-12565719-B2.md` / `intelligence_report_US-12565719-B2.md`
- `final_end_to_end_validation_summary.json`

ローカル開発（`DEMO_OUTPUTS_ROOT` 未設定）では従来どおり `outputs/` を参照します。

## デプロイ例

```bash
gcloud config set project devops-ai-agent-hackathon-2026

gcloud run deploy tech-cartography-v7-demo \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars SHOW_DEVELOPER_MODE=false,APP_DEFAULT_MODE=demo,DEMO_OUTPUTS_ROOT=demo_outputs,DISABLE_EXTERNAL_API=true,DISABLE_EMAIL_SEND=true,DISABLE_SCHEDULER=true
```

## ローカル Cloud Run 相当確認

```bash
PORT=8080 \
SHOW_DEVELOPER_MODE=false \
APP_DEFAULT_MODE=demo \
DEMO_OUTPUTS_ROOT=demo_outputs \
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

確認: `status: Evidence Map ready`、Selected Evidence Papers / Claim × Paper Links が空でないこと。

## 安全方針

- 外部 API は UI から自動実行しない（`DISABLE_EXTERNAL_API=true`）
- メール送信しない（`DISABLE_EMAIL_SEND=true`）
- scheduler / launchd / cron は Cloud Run 提出用では非表示
- 通常画面に `/Users/` ローカルパスを出さない（Phase 24.5 済み）

## 前フェーズ

Phase 24.5A〜F で Demo UI 安全化・ノイズ削減済み。Phase 24.6 でデプロイ骨格、24.6A で demo bundle 同梱を修正。
