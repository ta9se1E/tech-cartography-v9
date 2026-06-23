# Phase 25S — Watch Profile Management and Next Cycle Control

## Watch Profile とは

Watch Profile は週次特許インテリジェンスの **監視条件台帳** です。次を人間が承認したうえで保存します。

- 監視する技術テーマ（`theme_name` / `theme_description`）
- 検索語・クエリ・除外語・対象出願人・法域
- 次回対象とする公報・論文・Web Signal の方針（`source_policy` 等）
- 前回からの拡張候補（`expansion_candidates`）
- 次回実行時の優先度（`weekly_priority`）

**含めないもの:** FTO / 侵害 / 有効性判断、secret 値、外部 API 実行結果そのもの。

## active / draft / archive

| 状態 | 保存先 | 意味 |
|------|--------|------|
| `draft` | `outputs/live_watch_profiles/drafts/` | 編集中・承認待ち |
| `active` | `outputs/live_watch_profiles/active/` | 現在有効な監視条件（原則1件） |
| `archived` | `outputs/live_watch_profiles/archive/` | 過去版・退避版 |

命名例: `watch_profile_active_YYYYMMDDTHHMMSS_run-xxxx.json`（`.md` も同時保存）

## draft 作成手順

1. admin で Live Operation Console または Analyst Input の **Watch Profile Management** を開く
2. `ENABLE_WATCH_PROFILE_MANAGEMENT=true` が Cloud Run に設定されていることを確認（デフォルト deploy は `false`）
3. フォームに `theme_name`、`search_keywords` / `search_queries` 等を入力
4. **Watch Profile draft を保存** — 外部検索は実行されません

## active 化手順

1. 最新 draft の内容を確認（diff 表示あり）
2. 確認文欄に **`ACTIVATE WATCH PROFILE`** を完全一致で入力
3. **Watch Profile を active 化** — 既存 active は自動で archive へ移動
4. Scheduler は起動しません。メール送信もしません。

## archive 手順

1. 確認文 **`ARCHIVE WATCH PROFILE`** を入力
2. **active Watch Profile を archive** — active がなくなるまで新規 dry-run は warning 付き

## rollback 手順

1. 現 active の `previous_profile_id` が archive に存在することを確認
2. 確認文 **`ROLLBACK WATCH PROFILE`** を入力
3. **previous Watch Profile へ rollback** — 現 active は archive へ退避後、previous を active 化

## Scheduler dry-run との関係

- Scheduler dry-run は **active Watch Profile の path** を参照し、計画 artifact に `active_watch_profile_path` を残します
- `planned_steps` に Watch Profile 確認ステップを含みます
- **Scheduler は起動しません**（`DISABLE_SCHEDULER=true` 維持）

## Digest Preview との関係

- Digest Preview 保存時、active profile があれば artifact に `active_watch_profile_path` / `active_watch_profile_id` を記録
- Next Cycle Search Plan から **draft 候補取り込み**可能（自動 active 化はしない）

## Run History 確認方法

`outputs/live_run_history/` に以下の `action_type` が記録されます。

- `live_watch_profile_draft_save`
- `live_watch_profile_activate`
- `live_watch_profile_archive`
- `live_watch_profile_rollback`
- `live_scheduler_dry_run`

各エントリに `profile_id`、`version`、`status`、`confirmation_matched`、safety フラグ（`no_external_api` 等）が含まれます。

## artifact 確認方法

Cloud Storage マウント配下（`LIVE_OUTPUTS_ROOT`）:

```
outputs/live_watch_profiles/drafts/
outputs/live_watch_profiles/active/
outputs/live_watch_profiles/archive/
outputs/live_scheduler_dry_run/
```

## 有効化コマンド（編集機能）

デフォルト deploy では `ENABLE_WATCH_PROFILE_MANAGEMENT=false`（状態表示のみ可）。

```bash
gcloud run services update "$SERVICE" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --update-env-vars ENABLE_WATCH_PROFILE_MANAGEMENT=true
```

確認文は env で上書き可能:

- `WATCH_PROFILE_ACTIVATION_CONFIRMATION=ACTIVATE WATCH PROFILE`
- `WATCH_PROFILE_ARCHIVE_CONFIRMATION=ARCHIVE WATCH PROFILE`
- `WATCH_PROFILE_ROLLBACK_CONFIRMATION=ROLLBACK WATCH PROFILE`

## 禁止事項

- 外部 API を実行しない
- メール送信しない
- Scheduler を起動しない
- 未承認の監視範囲拡張を自動 active 化しない
- member に active 化させない
- secret / OAuth / JWT / SMTP_PASSWORD を保存・表示しない
- IAP を OFF にしない（本番運用）
- `AUTH_PROVIDER_MODE=basic` への意図しない復帰
