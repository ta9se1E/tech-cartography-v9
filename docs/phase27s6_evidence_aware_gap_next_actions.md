# Phase 27S.6 — Evidence-aware Gap / Next Actions

## 目的

Phase 27S.5.4 の Claim-Example binding（`binding_version=phase27s54`）を入力に、
Gap / Next Actions を **Evidence-aware** に更新する。

Gap は「弱点」ではなく、次の観点を整理する:

- 未確認事項
- 人手確認が必要な論点
- 次に読むべき箇所
- 次に取得すべき証拠候補
- 次の調査アクション

## 入力

- `cases/{case_id}/claims_input.csv`
- `outputs/local_v8_claim_example_links/{case_id}_*/claim_example_links.csv`
- `outputs/local_v8_claim_example_links/{case_id}_*/claim_example_binding_summary.csv`
- （任意）`example_facts.csv`, section / OCR CSV

外部 API（Gemini / Vision / Google Patents 自動取得）は呼ばない。

## Gap 分類

| gap_type | 条件 |
| --- | --- |
| `no_example_facts_gap` | `no_example_support_candidate` / `support_level=none` |
| `claim_example_link_gap` | `linked_fact_ids` と `top_evidence_snippets` が空 |
| `ocr_human_review_gap` | `needs_human_review=True` かつ根拠候補あり |
| `property_value_review_gap` | `property_value` / `property_candidate` |
| `table_review_gap` | `table_candidate` / `comparison_candidate` |
| `process_condition_review_gap` | `process_condition` |
| `structure_property_review_gap` | `structure_property` 等 |
| `paper_evidence_gap` | paper 出力がある場合のみ |
| `ready_for_human_review` | `high_candidate` + 根拠候補あり |

## 出力

`outputs/local_v8_gap_next_actions/{case_id}_{timestamp}_{hash}/`

- `gap_next_actions.csv`
- `gap_next_actions.md`
- `gap_next_actions_summary.csv`
- `gap_next_actions_summary.md`
- `human_review_checklist.md`
- `evidence_gap_manifest.json`（`generation_method=claim_example_evidence_phase27s6`）

## UI

- **Gap / Next Actions** タブ上部: Evidence-aware セクション
- **Top5 Deep Dive** 下部: 同セクション

ボタン:

- Generate Gap / Next Actions from Claim-Example Evidence
- Re-generate Gap / Next Actions（binding が新しい場合）

## 安全表現

禁止: 証明済み、裏取り完了、弱点、無効理由、FTO/侵害/有効性判断 等

使用: 裏取り候補、対応候補、未確認事項、人手確認が必要、原文確認が必要

## モジュール

- `src/tech_cartography/runtime/v8_evidence_gap_schema.py`
- `src/tech_cartography/services/v8_evidence_gap_next_actions.py`
- `src/tech_cartography/ui/v8_evidence_gap_next_actions_ui.py`
- `tests/test_v8_evidence_gap_next_actions_phase27s6.py`

## 検証

```bash
python -m pytest -q tests/test_v8_evidence_gap_next_actions_phase27s6.py
python -m compileall scripts src tests app.py
python scripts/check_v8_reframe_ready.py
```
