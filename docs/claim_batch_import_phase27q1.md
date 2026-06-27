# Claim CSV/Excel Batch Import — Phase27Q.1

## 目的

Top5 など複数特許の請求項本文を CSV/Excel で一括アップロードし、`claims_input.csv` に `manual_input` として反映します。

## 対応形式

- CSV (`.csv`)
- Excel (`.xlsx`)

## 必須列

| 列 | 説明 |
|----|------|
| `publication_number` | 公報番号（空なら reject） |
| `claim_no` | 請求項番号（空なら 1） |
| `claim_text` | 請求項本文（ユーザー提供のみ） |

## 任意列

`claim_source_url`, `claim_source_type`, `user_note`, `patent_title`, `language`, `source_file_name`

## 検証

- 空 claim / 短文 / `TBD` / `TODO` / `placeholder` / `claim text not loaded` → reject
- 同一 `publication_number` + `claim_no` の既存行 → `update` / `skip` / `append` を選択
- 既存 manual_input の上書きは `update` モード + UI 確認
- 適用前に `claims_input.csv` のバックアップを作成

## 出力

- `claims_input.csv`（更新）
- backup file
- `claim_batch_import_report.json` / `.md`
- `claim_batch_import_preview.csv`
- `rejected_rows.csv`

## CLI

```bash
conda run -n 2026hack python scripts/run_v8_claim_batch_import.py \
  --case-id case_01_pan_graphitization \
  --input-file path/to/top5_claims.xlsx \
  --mode validate

conda run -n 2026hack python scripts/run_v8_claim_batch_import.py \
  --case-id case_01_pan_graphitization \
  --input-file path/to/top5_claims.xlsx \
  --mode apply \
  --duplicate-mode update
```

## 禁止事項

- claim 本文の自動生成
- fake DOI / fake URL / fake claim の作成
- JP/CN claim 本文の BigQuery 取得
- FTO / 侵害 / 有効性判断

## Case 1 Top5 テンプレート

CN108286090A は既に manual_input あり。残り 4 件のテンプレートを Claim Map タブまたは Export タブからダウンロードできます。
