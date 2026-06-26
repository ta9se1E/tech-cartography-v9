# One Case Real Demo E2E Runbook — Phase27N.5

## 目的

Cloud Run deploy（Phase27O）の前に、**Case 1 だけ**実在特許 CSV で最後まで通し、ローカルデモとして説得力のある状態を作ります。

- **対象 Case:** `case_01_pan_graphitization`（PAN系炭素繊維の前駆体・炭化・黒鉛化）
- **Cloud Build / Cloud Run deploy:** この Phase では **実行しない**
- **外部 API / メール / Scheduler:** **実行しない**
- **claim 本文:** ユーザー提供のみ — **自動生成しない**

## 必要な入力 CSV

| 項目 | 値 |
|------|-----|
| 配置先 | `cases/case_01_pan_graphitization/large_candidates/case_01_bigquery_export_1000.csv` |
| 由来 | BigQuery 等で **別途抽出** した実在特許 CSV |
| 禁止 | fixture / 架空1000件 CSV / fake patent / fake URL / fake DOI |

CSV がない場合は処理を失敗扱いにせず、配置案内を表示して停止します。

## 手順（CLI）

### 1. 実在 CSV を配置

```bash
# 例: BigQuery エクスポート後
cp /path/to/your_export.csv \
  cases/case_01_pan_graphitization/large_candidates/case_01_bigquery_export_1000.csv
```

参考 SQL: `docs/bigquery_templates/case_01_pan_graphitization_1000.sql`（**アプリからは実行しない**）

### 2. One Case E2E 一括確認（推奨）

```bash
conda run -n 2026hack python scripts/run_v8_one_case_demo_e2e_check.py \
  --input-csv cases/case_01_pan_graphitization/large_candidates/case_01_bigquery_export_1000.csv \
  --max-rows 1000
```

### 3. 個別コマンド（必要に応じて）

**Import:**

```bash
conda run -n 2026hack python scripts/run_v8_large_candidate_import.py \
  --case-id case_01_pan_graphitization \
  --input cases/case_01_pan_graphitization/large_candidates/case_01_bigquery_export_1000.csv \
  --max-rows 1000
```

**Shortlist (Top100 / Top20 / Top5 + Ranking Explanation):**

```bash
conda run -n 2026hack python scripts/run_v8_large_candidate_shortlist.py \
  --case-id case_01_pan_graphitization
```

**Top5 確認:** stdout の `top5_publication_numbers` または `outputs/local_v8_large_shortlists/case_01_pan_graphitization/` 内 CSV

### 4. claim 本文を1件だけ手動投入

1. Streamlit: **Claim Map** タブ
2. Top5 のうち **1件** を選び、Google Patents / BigQuery / PDF / 手元資料から取得した **実 claim 本文** を投入
3. **システムは claim を生成しません**

### 5. Refresh（claim 投入後）

```bash
conda run -n 2026hack python scripts/run_v8_manual_claim_refresh.py \
  --case-id case_01_pan_graphitization \
  --publication-number <Top5の1件> \
  --claim-no 1
```

または E2E script が claim 検出時に自動 refresh します。

### 6. Demo Polish / Demo Readiness

```bash
conda run -n 2026hack python scripts/run_v8_demo_polish_pack.py \
  --case-id case_01_pan_graphitization

conda run -n 2026hack python scripts/run_v8_demo_readiness_check.py
```

E2E script に `--skip-demo-polish` / `--skip-readiness` で制御可能。

## UI で確認する順番

1. **はじめに** — Phase27N.5 / Case 1 最優先タスク
2. **入力** — CSV 取込（または CLI 済みなら Sources へ）
3. **Sources一覧** — 母集団確認（1000件 Deep Dive ではない）
4. **読むべき特許** — Top100 → Top20 → Top5
5. **Claim Map** — claim 状態 / 1件手動投入
6. **Evidence Map** — supporting evidence candidate
7. **Gap / Next Actions** — 未確認事項
8. **定点観測** — 次回タスク（メール/Scheduler は実行しない）
9. **Export** — Demo Polish / Demo Readiness / One Case E2E 状態

## 成功条件

- `source_candidates_large.csv` 投入済み（実データ）
- Top100 / Top20 / Top5 生成済み
- Top5 `publication_number` が表示できる
- claim 本文 **1件** 手動投入済み（望ましい）
- Claim Map / Evidence Map / Gap 再生成済み
- Demo Polish Pack / Demo Readiness Pack 生成済み
- Case 1 の `demo_readiness_status` が `not_ready` から改善

## 失敗時の切り分け

| 症状 | 確認 |
|------|------|
| `input_csv_exists=false` | CSV 配置パスを確認 |
| import 0件 | CSV 列名・publication_number を確認 |
| Top5 空 | shortlist ログ / large candidate 件数 |
| refresh 失敗 | claims_input.csv に claim 本文があるか |
| evidence/gap artifact_missing | 前段 refresh / 生成ボタン |

## 注意

- 1000件すべてを Deep Dive しない — **Top5 のみ**
- Evidence Map is not proof
- Gap is not invalidity
- Cloud Run deploy は **Phase27O** まで実行しない
