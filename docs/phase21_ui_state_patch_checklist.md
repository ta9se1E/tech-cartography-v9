# Phase 21 — UI smoke test checklist（session_state パッチ）

手動確認用チェックリスト。`streamlit run app.py` で実施してください。

## 起動・ログイン

- [ ] `streamlit run app.py` で起動できる（`StreamlitAPIException` が出ない）
- [ ] メールアドレスでログインできる
- [ ] コンソールに `easy_pipeline_root_input` の session_state / default value 二重管理 warning が出ない

## Widget session_state ルール（Patch 2）

- [ ] **すべての widget key**（`easy_pipeline_root_input` / `selected_run_id_input` / `display_mode_input` など）で、`value=`（または `index=` の二重指定）と `st.session_state[key] = ...` の**二重初期化をしない**
- [ ] 初期値は widget 生成**前**に `if key not in st.session_state: st.session_state[key] = ...` または `setdefault` で入れる
- [ ] widget 生成時は `key=` のみ（`value=` は付けない）
- [ ] widget 生成**後**に widget key へ直接代入しない（`STATE_PENDING_*` + `apply_pending_widget_state_updates()` を使う）

## run_id / latest_run

- [ ] sidebar の **latest_run を読み込む** を押しても画面が落ちない
- [ ] 押下後、run_id 入力欄に latest_run の run_id が反映される
- [ ] run_id を手入力しても画面が落ちない
- [ ] 手入力後、内部状態（タブ表示・manifest 読み込み）が選択 run に追従する

## 7タブ UI

- [ ] 7タブが表示される
- [ ] **はじめる** タブを表示できる（デモストーリーカード）
- [ ] **特許候補** タブを表示できる
- [ ] **全文確認** タブを表示できる（`AttributeError: 'str' object has no attribute 'get'` が出ない）
- [ ] **全文確認** タブで `fulltext_retrieval_records` がある run を開いても落ちない（probe が str / dict / JSON 文字列のどれでも表示継続）
- [ ] **技術の裏取り** タブを表示できる（Evidence Map セクション）
- [ ] **レポート** タブを表示できる
- [ ] **設定** タブを表示できる

## Fulltext availability notice（堅牢化）

- [ ] `render_fulltext_availability_notice` は row / probe が `dict` / `str` / `None` / JSON 文字列のどれでも `AttributeError` を出さない
- [ ] 最低限の注意文（HTML）または空文字が返る

## 回帰確認

- [ ] ユーザー向け画面に金額・課金額は表示されない
- [ ] ログアウト後、再ログインできる

## 自動テスト（CI）

```bash
python3 -m compileall src scripts tests app.py
python3 -m pytest tests/test_streamlit_state_keys.py tests/test_easy_japanese_ui.py -q
```

期待:

- pending selected_run_id の apply が通る
- pending key は apply 後に pop される
- `app.py` に `st.session_state[WIDGET_SELECTED_RUN_ID] =` の直接代入がない
- `_coerce_mapping` / `render_fulltext_availability_notice` の堅牢化テストが通る
