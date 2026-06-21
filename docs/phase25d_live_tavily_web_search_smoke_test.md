# Phase 25D — Live Tavily Web Search Smoke Test

## 目的

Cloud Run **live** 上で、Tavily Web 検索を **admin 限定・1回・小さく** 実行できる smoke test を追加する。

- 特許検索パイプライン全体は回さない
- メール送信・scheduler は引き続き OFF
- 結果は Web Signal candidate（事実認定ではない）

## Tavily API key（Secret Manager）

```bash
echo -n "YOUR_TAVILY_KEY" | gcloud secrets create tech-cartography-tavily-api-key \
  --data-file=- \
  --replication-policy=automatic
```

既存 secret への version 追加:

```bash
echo -n "NEW_KEY_VALUE" | gcloud secrets versions add tech-cartography-tavily-api-key --data-file=-
```

**注意:** 実キーを docs / git / 画面 / ログに書かないでください。

## Cloud Run live へ secret を渡す

```bash
gcloud run services update tech-cartography-v7-live \
  --region us-central1 \
  --update-secrets TAVILY_API_KEY=tech-cartography-tavily-api-key:latest
```

初回は `--set-secrets` でも可。demo サービスには Tavily キーを入れない方針です。

## `DISABLE_EXTERNAL_API` の意味

| 値 | Tavily smoke test |
|----|-------------------|
| `true` | **実行不可**（キーがあっても API を呼ばない） |
| `false` | admin ログイン + `TAVILY_API_KEY` 設定時のみ実行可 |

live で smoke test を使う場合:

```bash
gcloud run services update tech-cartography-v7-live \
  --region us-central1 \
  --update-env-vars DISABLE_EXTERNAL_API=false
```

demo は `DISABLE_EXTERNAL_API=true` のまま維持してください。

## Live Web Search Smoke Test の使い方

1. live URL に admin でログイン（`REQUIRE_LOGIN=true`）
2. **入力・実行** タブを開く
3. 「Live Web Search Smoke Test（管理者向け）」expander を開く
4. 検索クエリを入力（例: `carbon fiber patent intelligence`）
5. `max_results` を 1〜3 に設定（search_depth は basic 固定）
6. **「Tavilyで1回検索」** をクリック

### 表示される結果

- title / url / snippet / score / provider / fetched_at

### 保存先

`outputs/live_search/`

- `tavily_smoke_<timestamp>.json`
- `tavily_smoke_<timestamp>.md`

保存内容: query, provider, fetched_at, max_results, results, safety_notice（**API キーは含めない**）

## API credit 注意

- ボタン 1 回 = Tavily Search API 1 回
- `max_results` は最大 3 に制限
- 本番運用前の疎通確認用。乱発しないこと

## まだ OFF のもの

- メール送信（`DISABLE_EMAIL_SEND=true`）
- scheduler（`DISABLE_SCHEDULER=true`）
- 自動週次実行
- Gemini / OpenAI 実行
- 特許検索パイプライン全体

## ローカル確認

### ガードのみ（API 呼び出しなし）

```bash
REQUIRE_LOGIN=true \
APP_DEFAULT_MODE=analyst \
TECH_CARTOGRAPHY_LOGIN_USERNAME=admin \
TECH_CARTOGRAPHY_LOGIN_PASSWORD='test-password' \
DISABLE_EXTERNAL_API=true \
DISABLE_EMAIL_SEND=true \
DISABLE_SCHEDULER=true \
TAVILY_API_KEY='dummy' \
streamlit run app.py
```

→ smoke test UI は表示されるが、実行は「外部API無効化中」で停止

### 手動の外部 API 確認（ローカルのみ）

```bash
REQUIRE_LOGIN=true \
APP_DEFAULT_MODE=analyst \
TECH_CARTOGRAPHY_LOGIN_USERNAME=admin \
TECH_CARTOGRAPHY_LOGIN_PASSWORD='test-password' \
DISABLE_EXTERNAL_API=false \
DISABLE_EMAIL_SEND=true \
DISABLE_SCHEDULER=true \
TAVILY_API_KEY='<real key in local env only>' \
streamlit run app.py
```

## 関連モジュール

- `src/tech_cartography/services/live_tavily_search.py`
- `src/tech_cartography/ui/live_tavily_search_ui.py`
- `src/tech_cartography/runtime/external_api_guard.py` — `check_live_tavily_smoke_allowed`

## curl 疎通確認（参考）

```bash
curl -sS -X POST "https://api.tavily.com/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TAVILY_API_KEY}" \
  -d '{"query":"carbon fiber patent intelligence","search_depth":"basic","max_results":1}'
```

`results` が返ればキーとネットワークは OK です。
