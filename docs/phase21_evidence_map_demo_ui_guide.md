# Phase 21.1 — Evidence Map デモモード UI ガイド

## 目的

US-12565719-B2 の Evidence Map を、Streamlit UI 上でワンクリック表示できるデモモードを提供します。
新しい BigQuery / OpenAlex 実行は行わず、既存 `outputs/` の成果物を安全に読み込んで表示します。

研究者や中小企業が、次に何を確認すべきかを迷わず見られる実務支援 UI です。

## デモモードの起動方法

1. `streamlit run app.py` で起動し、メールアドレスでログイン
2. サイドバーの **「デモモードで読み込む：US-12565719-B2 Evidence Map」** をクリック
   - または **はじめる** タブ上部の同じボタン
3. 画面上部にデモバナーが表示され、7タブが利用可能になります

内部状態（widget key は直接更新しません）:

- `demo_mode_enabled` = True
- `demo_publication_number` = US-12565719-B2
- `selected_run_id` = demo_us_12565719_b2
- `pending_selected_run_id` 経由で run_id 入力欄も次回描画前に同期

## 読み込む artifact 一覧

| キー | パス |
|------|------|
| evidence_map_synthesis_md | `outputs/evidence_map_synthesis/US-12565719-B2/evidence_map_synthesis.md` |
| evidence_map_synthesis_json | `outputs/evidence_map_synthesis/US-12565719-B2/evidence_map_synthesis.json` |
| evidence_map_items_csv | `outputs/evidence_map_synthesis/US-12565719-B2/evidence_map_items.csv` |
| selected_evidence_papers_csv | `outputs/openalex_limited_execution/selected_evidence_papers.csv` |
| claim_paper_candidate_links_csv | `outputs/openalex_limited_execution/claim_paper_candidate_links.csv` |
| paper_candidate_relevance_report_md | `outputs/openalex_limited_execution/paper_candidate_relevance_report.md` |
| openalex_execution_summary_md | `outputs/openalex_limited_execution/openalex_execution_summary.md` |

## 推奨する見せ方（タブ順）

1. **はじめる** — デモストーリーカード（Tech Cartography の流れ / Deep Dive 対象 / 注意）
2. **技術の裏取り** — Evidence Map の中心
   - Evidence Map Summary
   - Selected Evidence Papers
   - Claim × Paper Candidate Links
   - Evidence Gaps
   - Next Actions
3. **レポート** — `evidence_map_synthesis.md`（先頭表示）、関連 MD は expander

特許候補・全文確認タブはデモモードでは案内メッセージのみ（Evidence Map に集中）。

## 各セクションの見方

### Evidence Map Summary

- publication_number / synthesis_status / retrieval_route
- claim_element_count / selected_evidence_paper_count / claim_paper_link_count
- evidence_level / caveat
- JSON に無い項目は DataFrame 件数や既定値で補完（`not available` 表示）

### Selected Evidence Papers

- 実 OpenAlex 由来の論文候補（supporting evidence candidate）
- 論文は特許主張の**証明ではない**ことに注意

### Claim × Paper Candidate Links

- 請求項要素と論文候補の対応（claims_only 由来の weak / low / medium confidence）

### Evidence Gaps

- BigQuery fulltext 欠落、Manual Route、description 未入力などのギャップ

### Next Actions

- 技術者・専門家が次に取るべき確認ステップ

## missing artifact 時の挙動

- loader は例外を握りつぶさず `missing_artifacts` / `errors` に記録
- status: `ready` / `partial` / `missing` / `error`
- 画面は落とさず、利用可能な成果物だけ表示を継続
- バナーに「一部の成果物が見つかりませんでした」と表示

## 注意事項

- 論文は **supporting evidence candidate**（証明ではない）
- **claims_only** 由来のため confidence は最大 medium、基本は low/weak
- **FTO、侵害、有効性判断はしない**
- **専門家レビューが必要**
- **架空情報を本物のように見せない**
- 企業・市場シグナルで Synthetic demo signal を使う場合は必ず **"Synthetic demo signal"** と明記
- メール送信は未実装
- このデモは新しい API 実行を行わない（既存 outputs の表示のみ）

## 関連モジュール

- `src/tech_cartography/ui/evidence_map_demo.py` — loader / render
- `src/tech_cartography/ui/streamlit_session.py` — `activate_evidence_map_demo_state()`
- `docs/phase21_ui_state_patch_checklist.md` — session_state 回帰チェック
