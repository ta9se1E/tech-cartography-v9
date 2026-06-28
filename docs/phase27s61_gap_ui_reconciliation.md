# Phase 27S.6.1 — Gap UI Reconciliation / Demo Flow Cleanup

## 目的

Phase 27S.6 の Evidence-aware Gap を **主表示** にし、旧 Gap（Evidence Map ベース）を Legacy 折りたたみ表示に整理する。

## 変更概要

### Gap / Next Actions タブ

1. Evidence-aware Gap / Next Actions（主表示）
2. Summary cards + 説明
3. Claim-level gaps
4. Human Review Checklist
5. Top 3 Next Actions（Evidence-aware、重複排除）
6. Watch Profile / Digest / Artifact trace
7. Downloads（Evidence-aware 出力）
8. Legacy Gap artifact（折りたたみ、デモでは閉じる）

### Top5 解析状況

- CN108286090A: `Review-ready candidate` — Run OCR を出さない
- 他Top5: pipeline 状態に応じた next_action
- 「次PhaseでGapロジック更新」文言を削除

### Human Review Checklist

- `(publication, claim, snippet)` 単位で根拠候補を重複除去
- Review-ready / property-table / process / next extraction セクション構成

## モジュール

- `src/tech_cartography/ui/v8_gap_next_actions_ui.py`
- `src/tech_cartography/ui/v8_evidence_gap_next_actions_ui.py`
- `src/tech_cartography/services/v8_evidence_gap_next_actions.py`
- `src/tech_cartography/services/v8_top5_pdf_pipeline_status.py`
- `tests/test_v8_gap_ui_reconciliation_phase27s61.py`

## 検証

```bash
python -m pytest -q tests/test_v8_gap_ui_reconciliation_phase27s61.py
python -m pytest -q tests/test_v8_evidence_gap_next_actions_phase27s6.py
```
