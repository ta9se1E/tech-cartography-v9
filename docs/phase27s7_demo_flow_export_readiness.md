# Phase 27S.7 — Demo Flow / Weekly Watch / Export Readiness

## 目的

Phase 27S.6.1 までの Evidence-aware Gap 成果物を、提出デモの7タブフローに自然接続する。
新しいAI解析機能は追加しない。

## デモフロー

1. はじめに — Demo readiness
2. 読むべき特許 — Top5
3. Claim Map
4. Evidence Map
5. Gap / Next Actions — Evidence-aware 主表示
6. 定点観測｜Weekly Watch — watch proposal / digest preview / scheduler plan (demo OFF)
7. Export — Demo Export Bundle

## 変更概要

### Weekly Watch（定点観測）

- Evidence-aware Gap 出力を検出し、`watch_profile_update_proposal.md` / `digest_summary.md` を表示
- Top 3 Next Actions（Evidence-aware）を表示
- Digest preview（件名案 + digest_summary.md）
- Scheduler plan（demo OFF、実運用説明のみ）
- Legacy Fixed Point Observation Loop は折りたたみ

### Export

- **Demo Export Bundle** セクションを追加
- `outputs/local_v8_demo_export_bundle/{case_id}_{timestamp}_{hash}/` に成果物をコピー
- `demo_summary.md` / `demo_artifact_trace.md` / manifest を生成

### Demo readiness

- はじめに / Export に **Demo readiness（提出デモ）** カード
- CN108286090A の OCR / facts / binding / ev-gap を `ready` 判定
- Email / Scheduler は `demo_off`（正常状態）

## モジュール

- `src/tech_cartography/runtime/v8_demo_flow_export_schema.py`
- `src/tech_cartography/services/v8_demo_flow_export_readiness.py`
- `src/tech_cartography/ui/v8_submission_demo_readiness_ui.py`
- `src/tech_cartography/ui/v8_evidence_aware_watch_ui.py`
- `src/tech_cartography/ui/v8_fixed_point_observation_ui.py`
- `src/tech_cartography/ui/v8_intro_ui.py`
- `src/tech_cartography/ui/v8_export_ui.py`
- `src/tech_cartography/ui/v8_judge_mode_copy.py`
- `tests/test_v8_demo_flow_export_readiness_phase27s7.py`

## 検証

```bash
python -m pytest -q tests/test_v8_demo_flow_export_readiness_phase27s7.py
python -m compileall scripts src tests app.py
python scripts/check_v8_reframe_ready.py
```
