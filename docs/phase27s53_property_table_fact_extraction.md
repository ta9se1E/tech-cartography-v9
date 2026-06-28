# Phase 27S.5.3 — Chinese OCR Property / Table Fact Extraction Hardening

## 目的

Google Vision OCR 由来の中国語特許本文（例: CN108286090A）から、工程条件だけでなく**物性値・比較表・構造指標**を候補ファクトとして抽出できるようにする。

すべての抽出結果は候補であり、`needs_human_review=True` が基本です。

## 変更概要

### Section 抽出 (`v8_patent_section_extract.py`)

- 中国語表題ルール追加: `表1`, `性能对比表`, `对比表` 等
- `table_candidate` section_type を追加（OCR表崩れを保持、`needs_human_review=True`）
- 強度/模量/GPa/M55J 等のキーワード + 複数数値同居時に table_candidate を生成

### Gemini プロンプト (`v8_gemini_example_facts.py`)

- 中国語 OCR 向け指示: 物性値・比較表・構造指標の抽出
- 本文にない値は生成禁止
- 曖昧な場合は `property_candidate` / `table_candidate` + evidence_text 保持

### Post-processing

- `normalize_example_fact_type()` — unknown 再分類
- `normalize_property_name()` — 拉伸强度 → `tensile_strength` 等
- `normalize_property_unit()` — GPa/MPa/℃/min 正規化
- `classify_property_candidate()` — 表・比較・構造指標の再分類

### Summary 列追加 (`example_facts_summary.csv`)

| 列 | 説明 |
|----|------|
| `structure_property_fact_count` | 取向角・微晶尺寸等 |
| `table_candidate_count` | 表候補 |
| `comparison_candidate_count` | 比較表行候補 |
| `property_candidate_count` | 値不明瞭な物性候補 |
| `unknown_fact_count` | 未分類 |

既存列（`property_fact_count`, `process_condition_fact_count` 等）は維持。

## UI

Top5 Deep Dive / Example Facts UI に以下を表示:

- fact_count, process_condition_fact_count, property_fact_count
- structure_property_fact_count, table_candidate_count, unknown_fact_count
- 警告: 「OCR由来の表・物性値抽出は候補です…」

## 安全表現

- OCR/Gemini 結果は候補 — 原文 PDF 確認必須
- 推定・補完・外挿しない
- Evidence は証明ではない / Gap は弱点ではない

## 再実行

OCR 本文 → section 抽出 → **Extract example facts with Gemini** を再実行してください。
Vision API / Gemini は明示ボタン操作時のみ。
