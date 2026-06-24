# Phase 25T — Controlled External API Web Signal Collection

## 目的

active Watch Profile の検索条件（`search_queries` / `search_keywords`）を使い、**admin が手動で** Tavily 経由の Web Signal **候補**を少量収集します。

- Cloud Scheduler 自動実行なし
- 自動メール送信・一斉送信なし
- 件数・クエリ数・テーマを env と Watch Profile で制限

## active Watch Profile が必要な理由

監視条件の台帳（Phase 25S）と一致した query のみ実行するためです。未承認の検索範囲拡張を防ぎます。

## 外部 API をデフォルト OFF にする理由

コスト・使用量・誤実行リスクを抑えるため、`DISABLE_EXTERNAL_API=true` かつ `ENABLE_MANUAL_WEB_SIGNAL_COLLECTION=false` が deploy デフォルトです。

## 手動有効化手順

```bash
gcloud run services update "$SERVICE" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --update-env-vars "ENABLE_MANUAL_WEB_SIGNAL_COLLECTION=true,DISABLE_EXTERNAL_API=false,WEB_SIGNAL_MAX_QUERIES=3,WEB_SIGNAL_MAX_RESULTS_PER_QUERY=5"
```

前提: active Watch Profile が `outputs/live_watch_profiles/active/` に存在すること。

## 手動無効化手順

```bash
gcloud run services update "$SERVICE" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --update-env-vars "ENABLE_MANUAL_WEB_SIGNAL_COLLECTION=false,DISABLE_EXTERNAL_API=true"
```

## 実行手順

1. admin で IAP ログイン
2. Live Operation Console → **Web Signal 手動収集**
3. 実行予定 query を確認（上限 `WEB_SIGNAL_MAX_QUERIES`）
4. 確認文 **`COLLECT WEB SIGNALS`** を完全一致入力
5. **Web Signal候補を手動収集** をクリック

## artifact 確認方法

`LIVE_OUTPUTS_ROOT/live_web_signals/`:

- `live_web_signal_collection_success_*.json` / `.md`
- `live_web_signal_collection_skipped_*.json`（ブロック時も保存）

各 signal は `confidence_label=candidate` です。

## Run History 確認方法

`action_type=live_web_signal_collection` — `result_count`, safety フラグ, artifact paths を記録。

## 重要な注意

- Web Signal は **候補情報** であり、確定事実ではありません
- **法的判断・FTO・侵害・有効性判断ではありません**
- Scheduler / メール送信とは **別操作** です
- Digest Preview / Scheduler dry-run は artifact を **参照するのみ**（自動 Tavily 呼び出しなし）

## コスト/使用量設計

| env | デフォルト | 意味 |
|-----|-----------|------|
| `WEB_SIGNAL_MAX_QUERIES` | 3 | 1回の収集で最大 query 数 |
| `WEB_SIGNAL_MAX_RESULTS_PER_QUERY` | 5 | query あたり最大結果数 |
| `WEB_SIGNAL_ALLOWLIST_DOMAINS` | (空) | 指定時のみ許可 domain |
| `WEB_SIGNAL_BLOCKLIST_DOMAINS` | (空) | 除外 domain |

## 禁止事項

- deploy デフォルトで外部 API ON にしない
- Scheduler / Digest Preview から自動 Tavily 実行しない
- メール送信・Scheduler 起動しない
- Watch Profile 自動 active 化しない
- active Watch Profile なしで実行しない
- secret / TAVILY_API_KEY を artifact に保存しない
- FTO / 侵害 / 有効性判断ラベルを付けない
