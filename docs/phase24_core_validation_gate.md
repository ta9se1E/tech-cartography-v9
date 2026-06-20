# Phase 24.4 — Core Validation Gate (Freeze前)

## なぜFreeze前にCore Validation Gateを挟むのか

Phase 24.2/24.3 でメール送信・週次スケジュールが先行した一方、レビューでは以下が指摘されました。

1. Link Candidate スコア補正（Phase 23.4.1）の確認結果が README / 進捗資料に明記されていない
2. US-12435451-B2 / US-12516451-B2 の Manual Claims 投入による再現性検証が未完了に見える
3. コア価値（Evidence Map / Link / Strategic Watch）の再現性確認より運用機能が先行して見える
4. MVP Freeze 前に「1件成功 / 複数件 / 未検証」を正直に記録すべき

Phase 24.4 は新機能追加ではなく、**既存 outputs を読み、検証レポートを生成する**ゲートです。

## レビューコメントへの対応方針

| 指摘 | 対応 |
|------|------|
| Link score 全件100点問題 | `link_score_calibration_summary_*.md/json` で分布確認 |
| 3件再現性 | `reproducibility_status_report.*` で status 明示 |
| コア価値の優先 | freeze_readiness で SMTP/scheduler は運用補助と明記 |
| Freeze判断 | `freeze_readiness_judgement.md` で limitations 付き ready |

## Link Candidateスコア補正確認

対象 CSV:

- `outputs/web_signal_links/{pub}/web_signal_link_candidates.csv`（優先）
- high / top / weak priority CSV もフォールバック

`all_100_problem_resolved`:

- 全件 score=100 → **false**
- 複数レンジに分布 → **true**

## 3件再現性確認

| 特許 | 期待 status |
|------|-------------|
| US-12565719-B2 | `complete_existing_demo` |
| US-12435451-B2 | `blocked_missing_manual_claims` |
| US-12516451-B2 | `blocked_missing_manual_claims` |

**1/3件完全検証、2/3件は Manual Claims 未投入で停止** — 失敗ではなく blocked と明記。

## 独自テーマ検証

`config/theme_validation_cases.example.json` をコピーし、独自テーマを記入:

```bash
cp config/theme_validation_cases.example.json config/theme_validation_cases.json
python scripts/run_theme_validation_smoke.py \
  --theme-config config/theme_validation_cases.json \
  --theme-id my_original_theme_001 \
  --dry-run
```

デフォルト `--no-external-api=True` — 既存 outputs のみ参照。

## 1件完全成功でもMVPとしてどう説明するか

- US-12565719-B2 を **reference complete demo** と位置づける
- 追加2件は **manual claims required** で次ステップが明確
- 別テーマは smoke test で段階確認（Stage 0–8）

## blocked_missing_manual_claims の扱い

失敗ではなく **未実施（blocked）**。`next_manual_claims_checklist.md` の import 手順が次アクション。

## Phase 25に進む条件

推奨: **Freeze ready with declared limitations**

- Core Validation Pack 生成済み
- Link score 分布確認済み
- 3件 status が文書化済み
- 制限事項が README / demo / known limitations patch notes に反映予定

## CLI

```bash
# Core Validation Pack
python scripts/build_core_validation_pack.py \
  --publication-numbers US-12565719-B2 US-12435451-B2 US-12516451-B2

# Theme smoke (dry-run)
python scripts/run_theme_validation_smoke.py \
  --theme-config config/theme_validation_cases.example.json \
  --theme-id pan_carbon_fiber_reference \
  --dry-run
```

## 禁止事項

- SMTP / scheduler 追加改修
- Cloud Run / Cloud SQL / Gmail API / OAuth
- UIからの外部API実行
- FTO / 侵害 / 有効性判断
