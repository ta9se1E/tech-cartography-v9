# Phase 27S.5 — Google Vision OCR Fallback

## 目的

pypdf でテキスト抽出できない Top5 公報 PDF（`needs_ocr=True`）に対し、Google Cloud Vision OCR を**明示ボタン操作時のみ**実行し、`publication_fulltext_raw.csv` 互換形式で出力する。

OCR 結果は候補テキストであり、確定本文ではありません。Gap ロジック更新・claim-example 再評価・裏取り完了判定は行いません。

## GCP 前提条件

- API: `vision.googleapis.com`, `storage.googleapis.com`
- サービスアカウントに GCS 読み書き + Vision OCR 権限
- Cloud Run 公開デモ: `ENABLE_GOOGLE_VISION_OCR=false`（デフォルト OFF）
- ローカル検証: ADC または `gcloud auth application-default login`

## 環境変数

| 変数 | 例 | 説明 |
|------|-----|------|
| `ENABLE_GOOGLE_VISION_OCR` | `false` / `true` | OCR 実行可否 |
| `GOOGLE_CLOUD_PROJECT` | `devops-ai-agent-hackathon-2026` | GCP プロジェクト |
| `GOOGLE_VISION_OCR_GCS_BUCKET` | `tech-cartography-v8-ocr-...` | 入出力 bucket |
| `GOOGLE_VISION_OCR_GCS_PREFIX` | `tech-cartography-v8/ocr` | GCS プレフィックス |
| `GOOGLE_VISION_OCR_MAX_PAGES` | `20` | 最大ページ（参考） |
| `GOOGLE_VISION_OCR_TIMEOUT_SEC` | `300` | OCR 待機タイムアウト |

## ローカルで ON にする

```bash
export ENABLE_GOOGLE_VISION_OCR=true
export GOOGLE_CLOUD_PROJECT=devops-ai-agent-hackathon-2026
export GOOGLE_VISION_OCR_GCS_BUCKET=tech-cartography-v8-ocr-devops-ai-agent-hackathon-2026-ta9se1
export GOOGLE_VISION_OCR_GCS_PREFIX=tech-cartography-v8/ocr
export GOOGLE_VISION_OCR_MAX_PAGES=20
export GOOGLE_VISION_OCR_TIMEOUT_SEC=300
streamlit run app.py
```

## OCR 対象

- Top5 特許 PDF のうち pypdf 抽出後 `needs_ocr=True` のもの
- **1 件ずつ**実行（一括 OCR なし）
- Google Patents からの PDF 自動取得は行わない

## GCS 入出力

入力例:

`gs://{bucket}/{prefix}/{case_id}/{publication_number}/input/{publication_number}.pdf`

出力例:

`gs://{bucket}/{prefix}/{case_id}/{publication_number}/output/`

## 複数JSONの集約（Phase 27S.5.1）

Vision OCR は PDF 1ページごとに `output-N-to-N.json` を出力する場合があります。
各 JSON の `responses[].fullTextAnnotation.text` を**1 response = 1 page** として自然順ソートで集約します。

`Rebuild OCR CSV from existing raw JSON` ボタンで、API を再実行せず `raw_vision_json` から CSV を再生成できます。

`outputs/local_v8_google_vision_ocr/{case_id}_{timestamp}_{hash}/`

- `google_vision_ocr_pages.csv`
- `google_vision_ocr_summary.csv`
- `publication_fulltext_raw.csv`（S.1 互換）
- `raw_vision_json/`

`publication_fulltext_raw.csv` の OCR 行:

- `extraction_method=google_vision_ocr`
- `needs_ocr=false`
- `warning=OCR text requires human review`

## S.2 セクション抽出との接続

`find_publication_fulltext_raw_pack()` が pypdf / OCR 出力を比較し、`prefer_ocr=True` の場合は OCR 本文を優先します。

OCR 本文（`publication_fulltext_raw.csv`）が存在し、セクション未生成または pypdf 由来セクションより新しい場合、Top5 Deep Dive に **Extract sections from OCR text** が表示されます。

CLI（UI 不使用時）:

```bash
python scripts/run_v8_section_extract_from_latest_ocr.py \
  --case-id case_01_pan_graphitization \
  --publication-number CN108286090A \
  --dry-run
```

## Phase 27S.5.2 — OCR セクション抽出導線

- pipeline status: `vision_ocr_text_extracted` を raw CSV からも判定
- `sections_stale_vs_ocr`: pypdf 由来セクションが残っていても OCR 再抽出を促す
- `needs_ocr=True` が残っていても OCR 本文があれば次アクションは section 抽出

## 安全表現

- OCR 結果は自動抽出テキスト — 誤読の可能性あり
- Evidence は証明ではなく裏取り候補
- Gap は弱点ではなく未確認事項
- FTO / 侵害 / 有効性判断は行わない

## 失敗時の対処

| 症状 | 対処 |
|------|------|
| `bucket_missing` | `GOOGLE_VISION_OCR_GCS_BUCKET` を設定 |
| `dependency_missing` | `pip install google-cloud-vision google-cloud-storage` |
| `auth_error` / permission denied | SA 権限・ADC を確認 |
| timeout | `GOOGLE_VISION_OCR_TIMEOUT_SEC` を増やすか PDF を分割 |
| `parse_failed` / no text | PDF 品質・スキャン解像度を確認 |
| JSON parse failed | GCS output JSON の存在を確認 |

## 費用注意

Vision Document OCR はページ課金があります。デモでは明示ボタン操作時のみ実行してください。
