# Submission Demo Operation Guide — Phase27Q.1

## 公開デモの推奨フロー

1. **Input タブ** — Case 1 を選択、研究テーマを確認
2. **BigQuery** — SQL を生成してダウンロード（直接実行は OFF）
3. BigQuery Console で手動実行 → 結果 CSV を **1000件候補 CSV/Excel** として取り込み
4. **Claim Map タブ** — Top5 claim テンプレートをダウンロード、ユーザー提供の claim 本文を CSV/Excel で一括投入
5. Claim Map / Evidence Map / Gap を再生成

## ハッカソン提出時の必須設定

Cloud Run 環境変数:

```
ENABLE_BIGQUERY_RUN=false
SHOW_BIGQUERY_ADMIN=false
BIGQUERY_DRY_RUN_ONLY=true
BIGQUERY_ALLOW_EXECUTE=false
ENABLE_EMAIL_SEND=false
ENABLE_SCHEDULER=false
DISABLE_EMAIL_SEND=true
DISABLE_SCHEDULER=true
```

## やらないこと（デモ）

- BigQuery 直接実行 UI を公開ユーザーに見せない
- claim 本文を AI 生成しない
- JP/CN claim を BigQuery から取得しない
- メール送信 / Scheduler 起動
- FTO / 侵害 / 有効性判断

## 管理者ローカル（任意）

BigQuery をローカルで実行する場合のみ:

```
ENABLE_BIGQUERY_RUN=true
SHOW_BIGQUERY_ADMIN=true
BIGQUERY_DRY_RUN_ONLY=false
BIGQUERY_ALLOW_EXECUTE=true
BIGQUERY_MAX_BYTES_BILLED=<安全な上限>
BIGQUERY_PROJECT_ID=<your-project>
```

必ず dry run で estimated bytes を確認してから execute してください。

## Case 1 実データ

- Top5: CN108286090A, CN117987966A, CN105401262A, CN105506785B, CN109402791B
- CN108286090A のみ manual_input claim 済み
- 残り 4 件は CSV/Excel テンプレートに claim 本文を貼り付けて投入
