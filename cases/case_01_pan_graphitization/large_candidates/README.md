# Large Candidates Input Folder — Case 1

## 目的

BigQuery 等で **別途抽出した実在特許 CSV** をここに置き、v8 の Large Candidate Import で取り込みます。

## ファイル例

- `case_01_bigquery_export_1000.csv` — BigQuery コンソールで dry-run 確認後にエクスポートした CSV

## 手順

1. `docs/bigquery_templates/case_01_pan_graphitization_1000.sql` を参考に BigQuery で抽出（**アプリからは実行しない**）
2. 抽出 CSV をこのフォルダに配置
3. 入力タブまたは CLI で import:

```bash
conda run -n 2026hack python scripts/run_v8_large_candidate_import.py \
  --case-id case_01_pan_graphitization \
  --input cases/case_01_pan_graphitization/large_candidates/case_01_bigquery_export_1000.csv \
  --max-rows 1000
```

4. staged shortlist:

```bash
conda run -n 2026hack python scripts/run_v8_large_candidate_shortlist.py \
  --case-id case_01_pan_graphitization
```

## 注意

- **架空特許 CSV を置かない**
- 1000件は **母集団** — 全件 Deep Dive しない
- Top100 / Top20 / Top5 の段階選抜後、Top5 のみ Claim Map / Evidence Map
- 外部 API / BigQuery 実行はこの Phase のアプリでは行わない
- FTO / 侵害 / 有効性判断ではない
