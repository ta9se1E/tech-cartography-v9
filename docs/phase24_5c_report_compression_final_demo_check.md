# Phase 24.5C — Report Compression & Final Demo Check

Phase 24.5A（モード分離）・24.5B（デモ表面 polish）の後、レポートタブを短く整理し Cloud Run 前チェックを追加したフェーズです。

## レポートタブ圧縮方針

**通常ユーザー向け（`render_compressed_report_tab`）**

| セクション | 内容 |
|-----------|------|
| Executive Summary | Intelligence Report から抜粋 |
| 今回の対象特許 | US-12565719-B2 + 短い説明 |
| Evidence Map の要点 | synthesis / report から最大6行 |
| 週次 Digest Preview の要点 | 重点監視 Top 抜粋 |
| 重点監視候補 | Digest から見出し列挙 |
| Final Validation（概要） | JP seed 3件 E2E 等の短い bullets |
| 次に確認すること | POLISHED_NEXT_ACTIONS |
| Download / Export | md / zip ボタン |

**開発者向け expander（デフォルト閉）**

- Core / Final Validation 技術ファイル（md / json / csv）
- Theme validation reports
- email draft / send log / scheduler / core validation pack
- 全文 Evidence Map レポート
- Reproducibility smoke
- Cloud Run 前チェックリスト

## 通常表示から隠した情報

- Core Validation Summary / Cross-Theme summary
- Final Validation JSON / freeze readiness technical report
- reviewer response
- send log / email draft raw body
- scheduler readme / launchd / cron / wrapper script
- 長い Markdown 全文

## メール下書き・送信ログの扱い

- **通常表示:** 非表示
- **開発者向け expander:** `render_email_draft_preview_section` / `render_send_log_section`
- Post-MVP 文言は docs に残す

## Final Validation 短縮表示

通常ユーザーには4行程度:

- JP seed N件で End-to-End 確認済み
- Paper / Web 実データあり
- freeze_readiness: MVPデモ可能
- Paper / Web / Link / Watch は確認候補

詳細 md / json / csv は開発者 expander 内。

## Cloud Run 前チェックリスト

`build_cloud_run_checklist()` — 8項目の静的チェック:

1. `/Users/` が通常 UI にない
2. 個人メール/SMTP が圧縮レポートにない
3. run_id が圧縮レポートにない
4. デモタブに theme_validation がない
5. 外部 API は明示同意のみ
6. scheduler が圧縮レポートにない
7. Review Pack 生成済み
8. docs に Post-MVP 記載

表示場所: レポートタブ開発者 expander / 設定タブ開発者 expander

## 関連ファイル

- `src/tech_cartography/ui/report_tab_ui.py`
- `src/tech_cartography/ui/v7_easy_app.py` — `_tab_reports`
- `tests/test_report_tab_compression.py`
- `tests/test_cloud_run_ready_ui.py`
