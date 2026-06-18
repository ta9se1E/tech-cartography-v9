# Phase 21 — Streamlit session_state キー設計

Tech Cartography v7 では、Streamlit widget key と internal state key を分離し、
widget 生成後の `StreamlitAPIException` を防ぎます。

定義元: `src/tech_cartography/ui/streamlit_session.py`

## Widget key 一覧（UI入力専用）

| 定数 | session_state キー | 用途 |
|------|-------------------|------|
| `WIDGET_PIPELINE_ROOT` | `easy_pipeline_root_input` | 実行結果フォルダ `st.text_input` |
| `WIDGET_SELECTED_RUN_ID` | `selected_run_id_input` | run_id `st.text_input` |
| `WIDGET_DISPLAY_MODE` | `easy_display_mode_input` | 表示モード `st.radio` |
| `WIDGET_WEEKLY_EMAIL` | `weekly_email_checkbox` | 週次メール設定 |
| `WIDGET_WEEKLY_DAY` | `weekly_email_day_input` | 送信曜日 |
| `WIDGET_WEEKLY_TIME` | `weekly_email_time_input` | 送信時刻 |
| `WIDGET_SETTINGS_DISPLAY_NAME` | `settings_display_name_input` | 設定: 表示名 |
| `WIDGET_SETTINGS_COMPANY_NAME` | `settings_company_name_input` | 設定: 会社名 |
| `WIDGET_EMAIL_DESTINATION_DISPLAY` | `weekly_email_destination_display` | メール送信先表示 |
| `WIDGET_WATCH_THEME_DISPLAY` | `weekly_watch_theme_display` | Watch テーマ表示 |

## Internal state key 一覧（アプリ内部専用）

| 定数 | session_state キー | 用途 |
|------|-------------------|------|
| `STATE_PIPELINE_ROOT` | `easy_pipeline_root` | 解決済みパイプライン出力ルート |
| `STATE_SELECTED_RUN_ID` | `selected_run_id` | **アプリが参照する run_id** |
| `STATE_DISPLAY_MODE` | `display_mode` | かんたん表示 / 詳細表示 |
| `STATE_MANIFEST_PATH` | `easy_manifest_path` | run_manifest.json パス |
| `STATE_SAVED_RUN_ID` | `easy_saved_run_id` | ユーザー保存済み run_id |
| `STATE_CURRENT_USER` | `current_user` | ログインユーザー |
| `STATE_WEEKLY_EMAIL_ENABLED` | `weekly_email_enabled` | 週次メール ON/OFF |

## Pending key 一覧（rerun 前の一時反映用）

| 定数 | session_state キー | 用途 |
|------|-------------------|------|
| `STATE_PENDING_SELECTED_RUN_ID` | `pending_selected_run_id` | latest_run 等で次回 rerun 時に入力欄へ反映する run_id |

`apply_pending_widget_state_updates()` が widget 生成**前**に pop し、
`STATE_SELECTED_RUN_ID` と `WIDGET_SELECTED_RUN_ID` へ反映します。

## 命名規則

- **Widget key**: `WIDGET_` プレフィックス + 説明的な名前（実キーは `*_input` など UI 向け）
- **Internal key**: `STATE_` プレフィックス + スネークケース
- **Pending key**: `STATE_PENDING_` プレフィックス（一時キュー、apply 後に削除）

## 禁止事項

1. **widget key は widget 生成後に直接変更しない**
   - 例（NG）: `st.text_input(..., key=WIDGET_SELECTED_RUN_ID)` の**後**に  
     `st.session_state[WIDGET_SELECTED_RUN_ID] = ...`
2. **internal 状態は `STATE_` 定数で管理する**
   - 画面本体・タブ描画は `st.session_state.get(STATE_SELECTED_RUN_ID)` を優先
3. **プログラムから入力欄を更新したい場合は `PENDING_` + `st.rerun()`**
   - latest_run ボタン → `STATE_PENDING_SELECTED_RUN_ID` 設定 → rerun
   - 次 run の先頭で `apply_pending_widget_state_updates()` を実行
4. **`app.py` 内で `st.session_state[WIDGET_SELECTED_RUN_ID] = ...` を直接書かない**
   - 例外: `apply_pending_widget_state_updates()` 内（widget 生成前のみ）

## 同期の流れ

```
[latest_run ボタン]
  → STATE_SELECTED_RUN_ID = run_id
  → STATE_PENDING_SELECTED_RUN_ID = run_id
  → st.rerun()

[次 run・widget 前]
  → apply_pending_widget_state_updates()
  → WIDGET_SELECTED_RUN_ID に反映

[run_id 手入力]
  → widget が WIDGET_SELECTED_RUN_ID を保持
  → STATE_SELECTED_RUN_ID = run_id_input.strip()
```
