# Phase 21 — UI smoke test checklist（session_state パッチ）

手動確認用チェックリスト。`streamlit run app.py` で実施してください。

## 起動・ログイン

- [ ] `streamlit run app.py` で起動できる（`StreamlitAPIException` が出ない）
- [ ] メールアドレスでログインできる

## run_id / latest_run

- [ ] sidebar の **latest_run を読み込む** を押しても画面が落ちない
- [ ] 押下後、run_id 入力欄に latest_run の run_id が反映される
- [ ] run_id を手入力しても画面が落ちない
- [ ] 手入力後、内部状態（タブ表示・manifest 読み込み）が選択 run に追従する

## 7タブ UI

- [ ] 7タブが表示される
- [ ] **はじめる** タブを表示できる（デモストーリーカード）
- [ ] **特許候補** タブを表示できる
- [ ] **全文確認** タブを表示できる
- [ ] **技術の裏取り** タブを表示できる（Evidence Map セクション）
- [ ] **レポート** タブを表示できる
- [ ] **設定** タブを表示できる

## 回帰確認

- [ ] ユーザー向け画面に金額・課金額は表示されない
- [ ] ログアウト後、再ログインできる

## 自動テスト（CI）

```bash
python3 -m compileall src scripts tests app.py
python3 -m pytest tests/test_streamlit_state_keys.py -q
```

期待:

- pending selected_run_id の apply が通る
- pending key は apply 後に pop される
- `app.py` に `st.session_state[WIDGET_SELECTED_RUN_ID] =` の直接代入がない
