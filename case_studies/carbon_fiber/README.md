## Carbon Fiber Evidence Map (Case Study)

このケーススタディは、炭素繊維（例: PAN系）に関する特許・論文Evidence Candidate・Web/企業シグナル候補を統合し、中小企業向けに「読むべき特許」「確認すべき裏取りギャップ」「次アクション」を整理するためのものです。

### One command pipeline（Phase 12）

安全側デフォルト（外部APIは実行しない）:

```bash
python scripts/run_carbon_fiber_evidence_map.py --config configs/carbon_fiber_pipeline.yaml
```

BigQuery light を実行する場合:

```bash
python scripts/run_carbon_fiber_evidence_map.py --config configs/carbon_fiber_pipeline.yaml --execute-bigquery
```

既存CSVから後段を再実行する例:

```bash
python scripts/run_carbon_fiber_evidence_map.py \
  --config configs/carbon_fiber_pipeline.yaml \
  --use-existing-light-csv outputs/bigquery_light_retrieval/latest/bigquery_light_results_dedup.csv \
  --start-stage technology_clustering_ranking
```

### 入力ファイル

- `configs/carbon_fiber_pipeline.yaml`（pipeline config）
- `configs/carbon_fiber_demo_profile.yaml`（検索・ランキングプロファイル）
- `case_studies/carbon_fiber/web_signals/*.csv`（手入力Web/企業シグナル）

### 出力ファイル（runごと）

`outputs/pipeline_runs/{run_id}/`

- `run_manifest.json` / `run_summary.md`（実行状況・入出力・スキップ理由）
- `artifact_index.json` / `artifact_index.md`（成果物一覧）
- `stages/*/`（各Phase相当の出力）
- 最終レポート（生成できた場合）: `carbon_fiber_evidence_map_v1.md`

### まだやらないこと

- 月次/隔週の自動更新
- メール送信
- Cloud Run / Cloud SQL / Scheduler
- 自動Web検索（Tavily等）

