# Phase 24.4B — Cross-Theme Core Validation Summary

## 目的

Phase24.4A で Streamlit 上の別テーマ検証 UI を使い、PAN系炭素繊維前駆体の表面・内部欠陥制御テーマについて seed 特許 3 件の Manual Claims 投入と Evidence Map skeleton 生成まで確認した結果を整理し、MVP Freeze 前の **Core Validation Summary** を生成する。

本 Phase は**新機能追加ではなく**、検証結果のドキュメント化と Freeze 判断の整理である。

## 検証テーマ

| 項目 | 値 |
|------|-----|
| theme_id | `pan_precursor_surface_internal_defects` |
| theme_name | PAN系炭素繊維前駆体の表面・内部欠陥制御 |

### Seed 公報（3件）

- JP2022090764A
- JP2023163084A
- JP2018084002A

## 確認済み（Stage 0〜3）

| Stage | 内容 | 結果 |
|-------|------|------|
| Stage 2 | Manual Claims 保存（ユーザー提供の公報原文） | 3/3 pass |
| Stage 3 | Evidence Map skeleton 生成 | 3/3 pass |

- 3 件とも Manual Claims 保存済み
- 3 件とも Evidence Map skeleton あり
- Streamlit「別テーマ検証」タブおよび Seed 進捗ダッシュボードで UI 上確認

## 未検証範囲（Stage 4 以降）

以下は**意図的に未実行**であり、サマリーに明記する。

- Stage 4: `paper_candidates_available`（論文候補）
- Stage 5: `web_signal_candidates_available`（Webシグナル候補）
- Stage 6: `link_candidates_available`（Link Candidate）
- Stage 7: `strategic_watch_available`（Strategic Watch）
- Stage 8/9: `digest_available`（Weekly Digest）
- OpenAlex / Tavily / BigQuery の自動実行
- UI からのメール送信・scheduler 登録

## 重要な注意

- **Evidence Map skeleton は最終 Evidence Map ではない**（論文・Web evidence 紐付けは未検証）
- Manual Claims はユーザーが公報原文から貼り付けたテキスト（AI 生成ではない）
- **FTO、侵害、有効性の法的判断ではない**
- 外部 API は本 Phase では実行しない

## Freeze 判断

**結論: `freeze_ready_with_declared_limitations`**

（制限を明記した上での MVP Freeze 可能）

### 理由

1. 既存デモ US-12565719-B2 は Weekly Digest まで通過（complete_existing_demo）
2. 別テーマ JP seed 3 件で Manual Claims → skeleton まで UI 上で再現確認（1 件偶然ではない）
3. Stage 4 以降・skeleton 制限・外部 API 未実行を README / デモ台本 / 既知制限に明記した上で Freeze 可能
4. DB 永続化は Post-MVP

## レビューコメントへの回答方針

| 指摘 | 回答 |
|------|------|
| Link Candidate 全件100点 | Phase23.4.1 で補正済み。README に補正サマリーを追記 |
| 1件だけの再現性 | US 1 件完全 + JP seed 3 件 Stage 3 まで（skeleton） |
| SMTP/scheduler 偏重 | Phase24.4A でコア検証に回帰。別テーマ UI 確認済み |
| Freeze 条件 | 制限明記で `freeze_ready_with_declared_limitations` |

## 生成物

```bash
python scripts/build_core_validation_summary.py \
  --theme-id pan_precursor_surface_internal_defects \
  --theme-name "PAN系炭素繊維前駆体の表面・内部欠陥制御" \
  --seed-publications JP2022090764A JP2023163084A JP2018084002A \
  --output-dir outputs/validation/core_validation
```

出力先: `outputs/validation/core_validation/`

- `cross_theme_core_validation_summary.md` / `.json`
- `freeze_readiness_judgement.md`
- `reviewer_response_notes.md`
- `readme_patch_notes.md`
- `demo_script_patch_notes.md`
- `known_limitations_patch_notes.md`

## モジュール

- `src/tech_cartography/validation/core_validation_summary.py` — `CoreValidationSummary` dataclass、集計、Markdown/JSON 生成
- `scripts/build_core_validation_summary.py` — CLI
- `tests/test_core_validation_summary.py` — ユニットテスト

## UI

レポートタブに Core Validation Summary の保存先パスと主要 3 ファイルのプレビューリンクを表示（外部 API・メール・scheduler は触らない）。
