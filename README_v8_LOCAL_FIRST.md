# README — v8 Local-First Development

## 作業場所

この v8 作業は **git worktree** 上で行います。

| 項目 | 値 |
|------|-----|
| 作業フォルダ | `/Users/esakitakusei/Documents/python/practice/portfolio/2026_Hackathon/PatentScout_AI_v8` |
| 元プロジェクト | `PatentScout_AI_v7`（**触らない**） |
| branch | `v8-claim-evidence-gap` |

```bash
cd /Users/esakitakusei/Documents/python/practice/portfolio/2026_Hackathon/PatentScout_AI_v8
git branch --show-current   # v8-claim-evidence-gap
```

## 開発方針

- **ローカルファースト**: Phase27B〜27I はローカルで分析品質を詰める
- **Cloud Build は節目だけ**: 日常開発では必須にしない（Phase27L で Cloud Run 反映）
- **3案件検証を最優先**: `cases/case_01_*` 〜 `case_03_*`
- **既存 v7 機能を削除しない**

## 必須で残す機能

以下は v8 でも **削除しない**（デフォルト OFF でも機能は保持）:

- **メール送信** — 定点観測ループの Digest 配信
- **Scheduler** — 定点観測の自動トリガー
- **Watch Profile** — 検索範囲管理
- **Scope Expansion / Feedback** — 範囲調整
- **Run History** — 操作追跡
- Cloud Storage artifact / Digest Preview

## やらないこと

- FTO / 侵害 / 有効性 / 法的結論
- 架空情報（fake evidence）の表示
- Deep Research API 本番導線
- Cloud SQL 追加
- メール送信・Scheduler・外部 API のデフォルト ON

## ローカル実行コマンド

```bash
cd /Users/esakitakusei/Documents/python/practice/portfolio/2026_Hackathon/PatentScout_AI_v8

# Streamlit アプリ
conda run -n 2026hack streamlit run app.py

# v8 Phase27A readiness
conda run -n 2026hack python scripts/check_v8_reframe_ready.py

# Phase27I: 3案件ローカル検証パック
conda run -n 2026hack python scripts/run_v8_three_case_validation_pack.py
```

## Phase27I — Three Case Validation Pack

3案件（case_01〜03）について、Sources → Patent Shortlist → Claim Map → Evidence Map → Gap / Next Actions → 定点観測 → Export の一連の流れをローカル検証します。

- 出力先: `outputs/local_v8_case_validation_packs/`
- **readiness_for_demo**: claim 本文未取得は `needs_claim_text`（架空 claim を作らない）
- 外部 API / メール送信 / Scheduler 起動は行わない
- **Cloud Build はこの Phase では実行しない**

次 Phase: Phase27K（UI 調整）→ Phase27L（Cloud Run 反映）

## Phase27J — Manual Claim Injection

claim 本文は **ユーザーが一次情報からコピーしたもののみ** を Claim Map タブで投入します。システムは生成しません。

```bash
conda run -n 2026hack python scripts/run_v8_manual_claim_refresh.py \
  --case-id case_01_pan_graphitization \
  --publication-number US5176959 \
  --claim-no 1
```

- 出力先: `outputs/local_v8_manual_claim_refresh/`
- `cases/<case_id>/manual_claim_workbench.md` を参照
- cases/ 配下に架空 claim は入れない

## Phase27J.0 — Large Candidate Import and 1000-scale Shortlisting

各 Case 最大 **1000件** の実在特許候補を CSV/Excel から取り込みます。1000件は母集団であり、全件 Deep Dive しません。

```bash
conda run -n 2026hack python scripts/run_v8_large_candidate_import.py \
  --case-id case_01_pan_graphitization \
  --input cases/case_01_pan_graphitization/large_candidates/case_01_bigquery_export_1000.csv \
  --max-rows 1000

conda run -n 2026hack python scripts/run_v8_large_candidate_shortlist.py \
  --case-id case_01_pan_graphitization
```

- 入力: `cases/<case_id>/large_candidates/` に BigQuery 等で抽出した実在特許 CSV
- BigQuery はアプリから **実行しない**（SQL テンプレートは `docs/bigquery_templates/` に参考のみ）
- 段階選抜: Top100 → Top20 → Top5
- Claim Map / Evidence Map は Top5 またはユーザー選択に限定
- fake patent / fake DOI / fake URL を作らない
- メール送信・Scheduler は必須機能として残す（本 Phase では実行しない）

**次 Phase:** Phase27J.1（UI polish）→ Phase27K（Manual Claim）→ Phase27L（Evidence polish）→ Phase27M（Cloud Run）

## テストコマンド

```bash
conda run -n 2026hack python -m compileall scripts src tests app.py
conda run -n 2026hack python -m pytest -q
conda run -n 2026hack python scripts/check_v8_reframe_ready.py
conda run -n 2026hack python scripts/run_v8_three_case_validation_pack.py
conda run -n 2026hack python scripts/run_v8_large_candidate_import.py \
  --case-id case_01_pan_graphitization \
  --input tests/fixtures/v8_large_candidate_fixture.csv \
  --max-rows 100
conda run -n 2026hack python scripts/run_v8_large_candidate_shortlist.py \
  --case-id case_01_pan_graphitization
```

## 3案件

| case_id | テーマ |
|---------|--------|
| `case_01_pan_graphitization` | PAN前駆体・炭化・黒鉛化 |
| `case_02_sizing_interface` | サイジング・界面・複合材 |
| `case_03_pressure_vessel_filament_winding` | CFRP圧力容器・FW・水素タンク |

各案件: `cases/<case_id>/case_profile.yaml`, `source_candidates.csv`, `expected_outputs.md`, `validation_checklist.md`

## Cloud 反映のタイミング

1. Phase27I で **3案件すべて** validation pack を生成し `readiness_for_demo` を確認
2. ローカル pytest + readiness 全 PASS
3. **Phase27L** で Cloud Build / Cloud Run deploy
4. それまでは v7 の本番環境を壊さない

## 関連ドキュメント

- `docs/v8_product_reframe.md` — サービス定義
- `docs/v8_three_case_validation_plan.md` — 検証計画
- `docs/v8_user_flow_and_tabs.md` — UI タブ設計
- `docs/v8_cursor_roadmap.md` — 実装ロードマップ
