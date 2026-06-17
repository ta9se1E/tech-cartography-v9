# Tech Cartography v7 Demo Guide

## 起動

```bash
streamlit run app.py
```

ログイン画面でメールアドレスを入力し、Easy Japanese UI（タブ型）でデモを進めます。

## デモで見せる順番

1. **ログイン** — 簡易メールログイン（OAuth・送信は未実装）
2. **はじめる** — Tech Cartographyのストーリー、Deep Dive対象、注意事項、Weekly Digest Preview
3. **特許候補** — BigQuery実特許検索結果、Top20、戦略監視（CN/EP/JP）
4. **全文確認** — BigQuery fulltext欠落診断、Manual Claims Route、US Top5
5. **技術の裏取り / Evidence Map** — Evidence Map Synthesis、Selected Papers、Claim×Paper Links、Evidence Gaps
6. **レポート** — Evidence Map Synthesis Report など
7. **設定** — Watch Profile、週次メール設定（送信は未実装）

## 見せるポイント

- BigQuery実特許検索（US Top候補）
- BigQuery fulltext欠落診断と Manual Route 推奨
- Manual Claims Route からの Claim Element 抽出
- claims-based paper query candidates
- OpenAlex limited execution と Source Quality
- Paper Candidate Relevance Filter（selected evidence papers）
- **Evidence Map** — 実OpenAlex論文タイトル / DOI / 引用数
- Claim × Paper fallback links（弱い対応の明示）
- Evidence Gaps と Next Actions
- Weekly Digest Preview（週次配信イメージ）
- CN/EP/JP Strategic Watch（手動確認ルート継続）

## デモ成果物のパス（自動検出）

以下が存在する場合、UIに表示されます。

- `outputs/evidence_map_synthesis/US-12565719-B2/evidence_map_synthesis.md`
- `outputs/evidence_map_synthesis/US-12565719-B2/evidence_map_items.csv`
- `outputs/openalex_limited_execution/selected_evidence_papers.csv`
- `outputs/openalex_limited_execution/claim_paper_candidate_links.csv`
- `outputs/openalex_limited_execution/paper_candidate_relevance_report.md`

再生成コマンド（必要時）:

```bash
python scripts/filter_openalex_paper_candidates.py \
  --paper-records outputs/openalex_limited_execution/openalex_paper_records.csv \
  --top-n 5 --publication-number US-12565719-B2

python scripts/build_evidence_map_synthesis.py \
  --publication-number US-12565719-B2 \
  --openalex-dir outputs/openalex_limited_execution
```

## 注意事項

- 論文は **supporting evidence candidate** であり、特許主張の証明ではない
- FTO / 侵害 / 有効性判断は行わない
- claims_only 由来の限界あり（description・実施例未入力時は裏取り精度が限定的）
- 専門家レビューが必要
- ユーザー向け画面に金額・課金情報は表示しない
- Cloud Run / 決済 / Gmail送信 / Google OAuth は未実装
