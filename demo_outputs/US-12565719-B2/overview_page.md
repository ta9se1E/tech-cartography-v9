# Tech Cartography — まとめページ

初見ユーザー向け: 各タブで何が分かるか、どこを見ればよいかを整理します。

## Important

Web signals are signal candidates, not final conclusions. Papers are supporting evidence candidates, not proof of patent claims. Strategic Watch Brief items are monitoring candidates, not final conclusions. This is not FTO, infringement, or validity analysis.

## はじめる

**目的**: Tech Cartographyの全体像、デモの見方、現在の分析状態を理解する。

**分かること**:

- このツールが何をするか
- Evidence Mapとは何か
- デモで見る順番
- 現在どこまで分析済みか

**主な成果物**:

- デモストーリーカード
- Reproducibility brief
- Weekly Digest Preview（旧）
- パイプライン stage status

**典型的な次アクション**: 初回はここから全体像を把握し、デモモードで Evidence Map を読み込む。

**注意**: Web signals are signal candidates, not final conclusions. Papers are supporting evidence candidates, not proof of patent claims. Strategic Watch Brief items are monitoring candidates, not final conclusions. This is not FTO, infringement, or validity analysis.

## 特許候補

**目的**: 多数の特許候補から、Deep Diveすべき対象を確認する。

**分かること**:

- 読むべき特許候補
- 技術テーマ
- ランクやクラスタ
- 次に全文確認すべき対象

**主な成果物**:

- ranked_patents.csv
- strategic_watch_candidates.csv
- cluster_summary.csv

**典型的な次アクション**: Deep Dive対象の特許を1件選び、全文確認タブへ進む。

**注意**: 候補リストは自動ランキングであり、最終選定ではありません。

## 全文確認

**目的**: 対象特許のclaims/descriptionが取得できているか確認する。

**分かること**:

- BigQuery fulltextが使えるか
- claims/description欠落の有無
- Manual Claims Routeが必要か
- manual投入済みか

**主な成果物**:

- fulltext_retrieval_status.csv
- manual_fulltext JSON
- fulltext_execute_summary

**典型的な次アクション**: claims欠落があれば Manual Claims Route で手動投入を検討する。

**注意**: 全文取得の成否はパイプライン状態であり、特許の価値判断ではありません。

## 技術の裏取り

**目的**: 請求項の技術要素、論文候補、Evidence Gap、Next Actionsを確認する。

**分かること**:

- Claim Element
- Selected Evidence Papers
- Claim × Paper Links
- Evidence Gap
- 技術者レビューすべき点

**主な成果物**:

- evidence_map_synthesis.md
- evidence_map_items.csv
- selected_evidence_papers.csv
- claim_paper_candidate_links.csv

**典型的な次アクション**: Claim Element と論文候補の対応を確認し、Evidence Gap を埋める次アクションを決める。

**注意**: 論文は supporting evidence candidate であり、特許主張の証明ではありません。

## 企業・市場シグナル

**目的**: Web情報、公的プロジェクト、IR、企業ニュース、Strategic Watch候補を確認する。

**分かること**:

- NEDO/JST/METIなど公的シグナル
- Money / National Project候補
- Web Signal Review
- Patent × Paper × Web Signal Link Candidate
- Strategic Watch Brief

**主な成果物**:

- web_signal_review_summary.md
- web_signal_link_candidates.csv
- strategic_watch_brief.md

**典型的な次アクション**: 高品質ソースの原文を開き、特許・論文との関係を人間が確認する。

**注意**: Web signals are signal candidates, not final conclusions. IR/disclosure requires document-level verification.

## レポート

**目的**: 各分析結果をMarkdownでまとめて読み、共有する。

**分かること**:

- Evidence Map Synthesis
- Reproducibility Summary
- Strategic Watch Brief
- Weekly Digest Preview
- Export Report / ZIP bundle

**主な成果物**:

- intelligence_report markdown
- weekly_digest_preview markdown/html
- digest_diff markdown
- tech_cartography_report_bundle.zip

**典型的な次アクション**: Intelligence Report をダウンロードし、チーム共有や週次レビューに使う。

**注意**: レポートは候補整理であり、FTO・侵害・有効性判断ではありません。

## 設定

**目的**: ローカル設定、メール設定、API設定の確認。

**分かること**:

- weekly digest設定
- APIキー設定の有無
- 出力先
- 送信ON/OFF状態

**主な成果物**:

- watch profile
- user settings
- weekly email preferences

**典型的な次アクション**: 監視テーマと週次メール設定を確認する（送信は Phase24.0 では無効）。

**注意**: メール送信は Preview only。実送信は今後の Phase で opt-in 実装予定。
