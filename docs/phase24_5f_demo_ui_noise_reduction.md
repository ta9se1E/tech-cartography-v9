# Phase 24.5F — Demo UI Noise Reduction Before Cloud Run

## 目的

Cloud Run 最小デプロイ前に、審査員・初見ユーザー向け画面から残っていた UI ノイズ（重複注意、長文 Markdown、内部値、`not available` 行）を削除する。

分析ロジック・データ生成・外部 API 処理は変更していません。

## 利用上の注意の重複削除

- **はじめる** タブでは expander 形式の「利用上の注意」を **1 回だけ** 表示（初期状態: 閉）
- デモ開始カード直後の二重 expander を解消
- 注意文の内容（Paper候補 / FTO 等）は `USAGE_NOTICE_LINES` に集約

## Strategic Watch Markdown

通常表示では以下のみ:

- Summary カード
- Top Strategic Watch Items テーブル
- 短い日本語要約

全文 Markdown は **「Strategic Watch Brief全文を表示」** expander（デフォルト閉）と **ダウンロードボタン** で参照。  
National Project / IR / Patent×Paper×Web の詳細表、Evidence Gaps、Next Actions、全文 subheader は **開発者向けモード** のみ。

## `not available` 行

Claim × Paper Candidate Links では `claim_element` / `claim_element_text` が空・`not available` の行を通常表示から除外。  
除外後 0 件の場合は Manual Claims 由来の限定的表示である旨を案内。開発者向けモードでは raw 表を expander で確認可能。

## 内部ステータス値の日本語変換

レポートタブの Final Validation 概要では `freeze_ready_*` / `actual_data` / `cross_theme_*` 等を `translate_report_status` で日本語化（例: MVPデモ可能、実データ取得済み）。

## 次ステップ

Phase 24.5F 完了後 → **Cloud Run Minimal Demo Deploy**
