# BigQuery Admin Runner — Phase27Q.1

## 目的

`ResearchThemeProfile` から Google Patents Public Dataset 向け SQL を生成し、**管理者限定**で dry run / execute により候補特許（最大 1000 件）を抽出します。

## 重要

- **候補メタデータ抽出のみ** — title / abstract / assignee / CPC / metadata
- **JP/CN の claim/description は取得しない**
- **claim 本文は CSV/Excel アップロードまたは手動入力のみ**
- **公開 Cloud Run ではデフォルト OFF / 非表示**

## 環境変数

| 変数 | デフォルト | 説明 |
|------|-----------|------|
| `ENABLE_BIGQUERY_RUN` | `false` | `true` でなければ dry_run / execute 拒否 |
| `SHOW_BIGQUERY_ADMIN` | `false` | UI で Dry Run / Execute を表示 |
| `BIGQUERY_PROJECT_ID` | — | GCP プロジェクト |
| `BIGQUERY_LOCATION` | `US` | クエリロケーション |
| `BIGQUERY_MAX_BYTES_BILLED` | `0` | 必須（未設定なら execute 拒否） |
| `BIGQUERY_DEFAULT_LIMIT` | `1000` | 最大結果数（上限 1000） |
| `BIGQUERY_DRY_RUN_ONLY` | `true` | execute 拒否フラグ |
| `BIGQUERY_ALLOW_EXECUTE` | `false` | execute 許可 |

## 実行モード

1. **generate_sql** — 認証不要、全ユーザー向け（UI / CLI）
2. **dry_run** — `ENABLE_BIGQUERY_RUN=true` + `BIGQUERY_MAX_BYTES_BILLED` 必須
3. **execute** — 上記 + `BIGQUERY_ALLOW_EXECUTE=true` + `BIGQUERY_DRY_RUN_ONLY=false`

## 安全設計

- execute 前に必ず dry_run
- `maximum_bytes_billed` を必ず設定
- Secret / 認証情報を UI に表示しない
- SQL injection 回避（エスケープ / リテラル）
- ハッカソン提出時: すべて OFF

## 出力

`outputs/local_v8_bigquery_runs/<case_id>/<timestamp>/`

- `generated_query.sql`
- `query_config.json`
- `query_summary.md`
- `dry_run_report.json` / `.md`
- `bigquery_results_raw.csv`
- `source_candidates_large.csv`（Large Candidate Import 互換）
- `query_manifest.json`

## CLI

```bash
conda run -n 2026hack python scripts/run_v8_bigquery_candidate_search.py \
  --case-id case_01_pan_graphitization \
  --theme-profile cases/case_01_pan_graphitization/research_theme_profile.json \
  --mode generate_sql
```

## スコアリング（読む優先度）

| 一致 | 点数 |
|------|------|
| core keyword | +3 |
| material/process keyword | +2 |
| application keyword | +1 |
| seed publication | +10 |
| exclude keyword | -10 |

法的価値・特許価値ではありません。

## ハッカソン提出時 Cloud Run 設定

```
ENABLE_BIGQUERY_RUN=false
SHOW_BIGQUERY_ADMIN=false
BIGQUERY_DRY_RUN_ONLY=true
BIGQUERY_ALLOW_EXECUTE=false
ENABLE_EMAIL_SEND=false
ENABLE_SCHEDULER=false
DISABLE_EMAIL_SEND=true
DISABLE_SCHEDULER=true
```
