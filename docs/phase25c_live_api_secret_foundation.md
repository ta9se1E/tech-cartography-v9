# Phase 25C — Live API Secret Foundation

## 目的

Cloud Run **live** サービスへ API キーを Secret Manager 経由で安全に渡し、アプリ側で **設定状態のみ** 確認できる土台を作る。

この Phase では **外部 API 実行は ON にしません**。`DISABLE_EXTERNAL_API=true` のまま、存在確認・ガード・管理者 UI のみ実装します。

## 対象 API キー

| 環境変数 | 用途（将来） |
|----------|--------------|
| `OPENAI_API_KEY` | LLM 呼び出し |
| `GOOGLE_API_KEY` | Google API / BigQuery 等 |
| `GEMINI_API_KEY` | Gemini |
| `TAVILY_API_KEY` | Web Signal 検索 |

値そのものはアプリ・ログ・画面・git に出しません。

## Secret Manager に secret を作成

```bash
# 例: OpenAI（値はローカルで設定し、コマンド履歴に残さないよう注意）
echo -n "YOUR_OPENAI_KEY" | gcloud secrets create tech-cartography-openai-api-key \
  --data-file=- \
  --replication-policy=automatic

# Gemini
echo -n "YOUR_GEMINI_KEY" | gcloud secrets create tech-cartography-gemini-api-key \
  --data-file=- \
  --replication-policy=automatic

# Tavily
echo -n "YOUR_TAVILY_KEY" | gcloud secrets create tech-cartography-tavily-api-key \
  --data-file=- \
  --replication-policy=automatic
```

**注意:** 上記 `YOUR_*` はプレースホルダです。実キーを docs や git に書かないでください。

## 既存 secret に version を追加

```bash
echo -n "NEW_KEY_VALUE" | gcloud secrets versions add tech-cartography-openai-api-key --data-file=-
```

## Cloud Run live へ `--set-secrets` で渡す

**demo サービスには API キーを入れない**方針です。live のみ設定します。

```bash
gcloud run services update tech-cartography-v7-live \
  --region us-central1 \
  --set-secrets \
OPENAI_API_KEY=tech-cartography-openai-api-key:latest,\
GEMINI_API_KEY=tech-cartography-gemini-api-key:latest,\
TAVILY_API_KEY=tech-cartography-tavily-api-key:latest
```

Cloud Run サービスアカウントに Secret Manager Secret Accessor ロールが必要です。

## `DISABLE_EXTERNAL_API=true` のまま確認する理由

- キー注入と UI 表示が正しいことを、**本番検索を走らせる前に** 検証できる
- 誤設定・漏洩リスクを最小化できる
- 次 Phase で最小 Live 検索を ON にする際、ガード解除だけで段階的に移行できる

## 管理者 UI での確認

live にログイン（`REQUIRE_LOGIN=true`、role=admin）後:

- **設定タブ** — 「API設定状態（管理者向け）」expander
- **サイドバー下部** — 同 expander（admin のみ）

表示内容:

- 各キーの configured / missing
- 外部 API 実行状態: disabled / enabled（env フラグ）
- 不足キー一覧
- API キー本体は表示しない旨の注意文

## セキュリティ注意

- API キーを画面・ログ・git・docs・テストに書かない
- `.env` は git add しない（ローカル検証のみ）
- `.env.example` には `<secret-manager-only>` プレースホルダのみ
- placeholder 値（`dummy`, `placeholder`, 空文字）は missing 扱い

## 次 Phase の方針

1. live で `DISABLE_EXTERNAL_API=false` に変更（demo は true のまま）
2. 最小 Live 検索（例: Tavily query plan → 限定実行）を ON
3. admin UI で configured を確認してから段階的に解放

## 関連モジュール

- `src/tech_cartography/runtime/api_secret_config.py`
- `src/tech_cartography/runtime/external_api_guard.py`
- `src/tech_cartography/ui/api_secret_status_ui.py`
- `scripts/check_live_beta_ready.py`
