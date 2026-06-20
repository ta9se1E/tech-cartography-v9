# Phase 24.5A — Demo Safe UI Core

Cloud Run 最小デプロイ前に、審査員・初見ユーザー向け画面から開発者情報を分離する UI 安全化フェーズです。

## UI モード（3 種）

| モード | 内部 ID | 用途 |
|--------|---------|------|
| デモを見る | `demo` | 完成済み outputs の閲覧のみ（デフォルト） |
| 本番実行 | `analyst` | 新テーマ分析・Manual Claims・E2E Chain |
| 開発者向け | `developer` | run_id / paths / validation / scheduler 参照 |

実装: `src/tech_cartography/ui/demo_safe_ui.py`  
セッション既定: `STATE_UI_MODE = "demo"`（`streamlit_session.default_app_session_state`）

## 通常画面から隠した情報

- ローカル絶対パス（`/Users/...`）→ `format_display_path()` で `outputs/...` 相対表示
- run_id（ヘッダー・サイドバー通常表示）
- latest_run 読み込み / デモ読み込みボタン
- 実行結果フォルダ入力
- Core / Final Validation Summary の技術ファイル一覧
- scheduler readme / launchd plist / cron sample / wrapper script
- send log / email draft 技術メタデータ

## タブ構成

**デモを見る:** はじめに / 技術の裏取り / 企業・市場シグナル / レポート / 設定

**本番実行・開発者向け:** 上記 + 特許候補 / 全文確認 / 本番実行（旧「別テーマ検証」）

## 警告文の集約

- 「はじめに」タブの **利用上の注意** expander に `USAGE_NOTICE_LINES` を集約
- 各タブ冒頭の長い warning/info box は削除または 1 行 caption に短縮
- 外部 API 実行ボタン付近のみ、明示同意チェックと短い警告を維持

## scheduler / launchd / cron

- **通常画面:** 非表示
- **開発者向けモード:** サイドバー expander および Delivery セクション（`developer_mode=True`）で参照可
- 文言: 「週次スケジューラーの Cloud Scheduler 連携は Post-MVP です」
- macOS launchd / cron はローカル検証用（Cloud Run 提出画面には表示しない）

## Cloud Run 前チェックリスト

- [ ] デフォルトが「デモを見る」
- [ ] サイドバー通常表示に `/Users/` がない
- [ ] run_id が通常表示にない
- [ ] デモモードで入力フォーム・本番実行タブがない
- [ ] 警告が「利用上の注意」に集約されている
- [ ] scheduler / send log が通常表示にない

## 関連ファイル

- `app.py` — `render_app_sidebar()` 呼び出し
- `src/tech_cartography/ui/v7_easy_app.py` — モード別タブ
- `src/tech_cartography/ui/delivery_ui.py` — `developer_mode` フラグ
- `tests/test_demo_safe_ui.py`
- `tests/test_sidebar_safe_mode.py`
