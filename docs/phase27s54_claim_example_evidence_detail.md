# Phase 27S.5.4 — Claim-Example Binding Evidence Detail

## 目的

Claim-Example binding の出力を「候補のまま」維持しつつ、デモ時に **どの claim がどの example のどの fact に対応するか** を見える化する。

## 変更概要

### Binding 単位

- `publication_number × claim × example group` でスコアリング
- `example_id` / `example_label` で fact を group 化
- 同一 claim に対して score 上位 1 example を主リンク

### Fact type 別スコア

| fact_type | カテゴリ |
|-----------|----------|
| process_condition | process |
| property_value / property_candidate | property |
| structure_property | structure |
| table_candidate / table_value | table |
| comparison_candidate / comparison_example | comparison |

### support_type

- `mixed_support_candidate` — 複数カテゴリ
- `process_support_candidate` / `property_support_candidate` / `structure_support_candidate`
- `table_support_candidate` / `comparison_support_candidate`
- `publication_level_support_candidate` — example_id なし
- `no_example_support_candidate`

### 出力 CSV 追加列

**claim_example_links.csv**

- `matched_fact_types`, `matched_fact_count`
- `process_match_count`, `property_match_count`, `structure_match_count`, `table_match_count`, `comparison_match_count`
- `selected_example_score`, `top_evidence_snippets`
- `process_evidence_texts`, `property_evidence_texts`, `structure_evidence_texts`, `table_evidence_texts`, `comparison_evidence_texts`
- `source_example_facts_csv`, `binding_version`

**claim_example_binding_summary.csv**

- `process_support_count`, `property_support_count`, `structure_support_count`, `table_support_count`
- `comparison_support_count`, `mixed_support_count`, `publication_level_support_count`
- `linked_fact_count`, `linked_example_count`, `source_example_facts_csv`

### reason 改善

例:

> claim 1 は Example 5 の工程条件・物性候補・表候補と対応する可能性があります。主な一致候補: …。根拠候補: 石墨化温度2480℃ / …。OCR由来の可能性があり、人手確認が必要です（候補）。

### UI

- Top5 Deep Dive / Claim-Example Binding UI に summary + claim 詳細テーブル
- **Re-run claim-example binding from latest example facts** — 最新 example_facts が binding より新しい場合

### 安全表現

- 対応は候補 — 法的判断ではない
- needs_human_review=True 維持
- OCR 由来数値は原文 PDF 確認必須

## 再実行

```bash
streamlit run app.py
```

Top5 Deep Dive → CN108286090A → **Re-run claim-example binding from latest example facts**
