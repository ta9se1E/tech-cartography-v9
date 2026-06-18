# Phase 23.2 — Web Signal Review Pack

## 目的

Phase 23.1 の Tavily Search / Extract Adapter で取得した Web 候補を、人間がレビューしやすい **Web Signal Review Pack** として整理します。

この Phase では **Patent × Paper × Web Signal の自動リンクは行いません**。  
Tavily 結果をそのまま Evidence Map に入れず、まず品質・種別・検証アクションを人間が確認できる形にします。

## なぜ Web Signal Review Pack が必要か

- Tavily 検索結果にはノイズが混ざる
- IR / disclosure は書類単位の確認が必須
- money / national_project はソース URL の確認が必須
- Human signal は誤認リスクが高い
- 同一 URL の重複や低品質候補をレビュー前に整理したい

## Tavily 実行結果をそのまま Evidence Map に入れない理由

- Web 情報は **signal candidate** であり最終結論ではない
- `verification_status` と `confidence` を人手で確認する段階が必要
- FTO / 侵害 / 有効性判断はこのワークフローの対象外
- 自動リンクは Phase 23.4 以降に段階的に追加する

## review_priority の考え方

`score_review_priority()` は 0〜100 のスコアを付けます。

**上げる条件**

- `source_quality` が high
- `national_project` / `money` / `grant` / `funding` など
- `ir_disclosure` / `disclosure`
- `public_funding` / `national_project` / `disclosure_platform` / `ir_official`
- PAN / carbon fiber / 炭素繊維 などの技術語
- `source_url` がある
- `evidence_sentences` がある

**下げる条件**

- `source_quality` が low / unknown
- `source_url` がない
- snippet / extracted_text が薄い
- job_board / social / blog 由来
- human signal
- `other` のまま evidence がない

## evidence_sentences の抽出方法

`extract_evidence_sentences()` は LLM を使わずルールベースで抽出します。

1. `raw_snippet` / `extracted_text` を文単位に分割
2. PAN / 炭素繊維 / NEDO / 決算説明 などのキーワードを含む文を最大 3 件抽出
3. 既存の `extracted_evidence_sentences` があれば優先利用

## IR / disclosure candidates の見方

- `ir_disclosure_candidates.csv` に `ir_disclosure` / `disclosure` タイプを集約
- `disclosure_type`（決算説明、統合報告書、適時開示など）を確認
- EDINET / JPX ドメインでも **本文確認前は verified_source にしない**

## money / national project candidates の見方

- `money_national_project_candidates.csv` に集約
- `national_project` / `money` / `grant` / `funding` / `equipment_investment`
- 公的機関ドメインでもリンク先ページの確認は必須

## rejected_or_low_quality_sources の意味

低価値候補をレビュー対象から外し、理由付きで保存します。

例:

- `missing_source_url`
- `missing_source_title`
- `low_quality_without_evidence`
- `other_type_without_evidence`
- `placeholder_invalid_domain`
- `thin_content`

削除ではなく監査用に CSV へ退避します。

## 実行コマンド例

Plan only + empty review pack:

```bash
python scripts/run_tavily_web_signal_search.py \
  --topic "PAN carbon fiber mid-temperature carbonization" \
  --categories national_project money ir_disclosure company local_news \
  --output-dir outputs/web_signals/tavily_pan_carbon_fiber \
  --max-queries 10 \
  --max-results-per-query 5 \
  --plan-only \
  --build-review-pack
```

Execute + review pack:

```bash
export TAVILY_API_KEY="your-key-here"

python scripts/run_tavily_web_signal_search.py \
  --topic "PAN carbon fiber mid-temperature carbonization" \
  --categories national_project money ir_disclosure company local_news \
  --output-dir outputs/web_signals/tavily_pan_carbon_fiber \
  --max-queries 10 \
  --max-results-per-query 5 \
  --execute-tavily \
  --extract-top-urls \
  --max-extract-urls 10 \
  --build-review-pack \
  --save-rejected
```

## API キー設定方法

```bash
export TAVILY_API_KEY="your-key-here"
```

- コードに直書きしない
- ログや出力 JSON に API キーを含めない

## 安全な実行上限

`--execute-tavily` 時は runner が以下に自動制限します。

| パラメータ | 上限 |
|-----------|------|
| max_queries | 10 |
| max_results_per_query | 5 |
| max_extract_urls | 10 |

- `human` カテゴリは実行から除外
- 失敗クエリがあっても全体は継続
- API レスポンスは raw JSON として保存

## 出力ファイル

```
outputs/web_signals/{batch_id}/review_pack/
  web_signal_review_pack.json
  web_signal_review_items.csv
  high_priority_web_signals.csv
  ir_disclosure_candidates.csv
  money_national_project_candidates.csv
  company_local_news_candidates.csv
  rejected_or_low_quality_sources.csv
  web_signal_review_summary.md
```

## 注意事項

- Web signals are signal candidates, not final conclusions.
- IR / disclosure signals require document-level verification.
- Human signals require careful identity verification.
- Money / national_project signals require source verification.
- This is not FTO, infringement, or validity analysis.
- Synthetic demo signal must be clearly labeled.
- Tavily results are retrieved web candidates and may include noise.

## 関連モジュール

- `src/tech_cartography/web_signals/review_pack.py`
- `src/tech_cartography/web_signals/tavily_runner.py`
- `scripts/run_tavily_web_signal_search.py`
