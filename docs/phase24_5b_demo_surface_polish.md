# Phase 24.5B — Demo Surface Polish

Phase 24.5A のモード分離を前提に、審査員向けデモ画面（はじめに / 技術の裏取り / 企業・市場シグナル）を読みやすく磨いたフェーズです。

## はじめにタブ改善

- **Tech Cartographyがやること** — 6ステップ（企業・市場シグナル連携を追加）
- **今回詳しく読む特許** — 旧「Deep Dive」を日本語化
- **どこを見れば何が分かるか** — タブごとの目的を追加
- **表示モードの違い** — デモ / 本番実行 / 開発者向けの短い説明
- **利用上の注意** — Phase 24.5A の expander に集約（run_id・BigQuery 内部事情は通常表示から除外）

## 技術の裏取り URL 追加

- `label_renderer.resolve_paper_url()` — doi → `https://doi.org/{doi}`、landing_page_url / openalex_id フォールバック
- Selected Evidence Papers / Claim × Paper Links に **論文を開く** 列（Markdown リンク、長い URL 文字列は非表示）

## Evidence Gaps / Next Actions 整理

`label_renderer.POLISHED_EVIDENCE_GAPS` / `POLISHED_NEXT_ACTIONS` に人間向けリストを固定。synthesis JSON との重複マージは停止。

## 企業シグナル日本語表示

- 冒頭に日本語説明カード（`SIGNAL_INTRO_JA`）
- 通常表示は **上位 3〜5 件**（タイトル / ドメイン / 種別 / なぜ見るべきか / 次に確認 / 原典URL）
- signal_id / review_priority / raw evidence → **開発者向け expander**
- 英語 summary → **英語詳細 / raw summary** expander

## 表記変換方針

`src/tech_cartography/ui/label_renderer.py` の `translate_label()` で一元化:

- claims_only → 請求項のみで判定
- supporting evidence candidate → 技術背景の確認候補
- national_project / money / ir_disclosure → 日本語候補ラベル
- query_plan_ready / actual_data → 検索計画作成済み / 実データ取得済み

## 関連ファイル

- `src/tech_cartography/ui/label_renderer.py`
- `src/tech_cartography/ui/evidence_map_demo.py`
- `src/tech_cartography/ui/web_signal_review_ui.py`
- `tests/test_evidence_url_renderer.py`
- `tests/test_signal_japanese_renderer.py`
- `tests/test_intro_tab_polish.py`
