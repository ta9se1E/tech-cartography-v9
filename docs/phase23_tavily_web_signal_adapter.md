# Phase 23.1 — Tavily Web Signal Adapter

## 目的

Phase 23.0 で整備した Web Signal Foundation の上に、**Tavily Search / Extract Adapter** を追加します。  
企業 IR・適時開示・有価証券報告書・決算説明資料などの **IR / Disclosure 情報** を Web Signal として扱える入口を作り、特許・論文・Web 情報をつなぐ外部 Web 情報取得基盤の第一段階とします。

## なぜ Tavily を使うか

- Search API で公開 Web 上の候補 URL / スニペットを安全に取得できる
- Extract API で URL 単位の本文候補を追加取得できる
- 専用 SDK を必須依存にせず、`urllib` ベースの薄い Adapter で接続できる
- **デフォルトでは API を実行しない** 設計と相性が良い

## Search / Extract の役割

| API | 役割 |
|-----|------|
| Tavily Search | クエリに対する検索結果（title, url, snippet）を signal candidate に変換 |
| Tavily Extract | 上位 URL の本文候補を `extracted_text` / `extracted_evidence_sentences` に付与 |

どちらも **最終結論ではなく signal candidate** として保存します。

## IR / Disclosure signal の扱い

- `signal_type = ir_disclosure`（または `disclosure`）として分類
- `disclosure_type` を title / snippet から推定（決算説明、統合報告書、有価証券報告書、適時開示など）
- `verification_status = needs_human_review` を原則とする
- `confidence` は **medium まで**（EDINET / JPX ドメインでも `verified_source` にはしない）
- 本文・書類単位の確認後にのみ `verified_source` へ上げる設計

## EDINET / TDnet / 企業公式 IR の扱い

| ソース | この Phase での扱い |
|--------|---------------------|
| EDINET 関連ドメイン | `source_category=disclosure_platform`, `source_quality=high` の候補 |
| JPX / TDnet 関連 | 同上。Tavily 検索結果として拾うのみ |
| 企業公式 IR ページ | URL パスや title から `ir_official` 候補 |

## なぜ EDINET API / TDnet API 専用対応をまだ行わないか

- まず signal candidate / verification / caveat の枠組みで安全に受け止める
- 書類 ID・提出日・銘柄コードの厳密紐付けは専用 API 連携が必要
- 無秩序なスクレイピングや大規模クロールを避ける
- 専用 API 対応は **Phase 23.2 以降** に段階的に追加する

## dry-run / plan-only / execute-tavily の違い

| モード | API 実行 | 出力 |
|--------|----------|------|
| `--dry-run` | しない | 標準出力に計画のみ |
| `--plan-only`（デフォルト） | しない | `web_signal_queries.json` 等を保存 |
| `--execute-tavily` | する（要 API キー） | 検索 raw + WebSignal batch を保存 |

`--extract-top-urls` は execute 時のみ、上位 URL に対して Extract を追加実行します。

## API キー設定方法

```bash
export TAVILY_API_KEY="your-key-here"
```

- コードに API キーを直書きしない
- キーがない場合は `--execute-tavily` 時に分かりやすく停止する

## 実行コマンド例

Dry run:

```bash
python scripts/run_tavily_web_signal_search.py \
  --topic "PAN carbon fiber mid-temperature carbonization" \
  --categories national_project money ir_disclosure company local_news \
  --max-queries 10 \
  --max-results-per-query 5 \
  --dry-run
```

Plan only:

```bash
python scripts/run_tavily_web_signal_search.py \
  --topic "PAN carbon fiber mid-temperature carbonization" \
  --categories national_project money ir_disclosure company local_news \
  --output-dir outputs/web_signals/tavily_pan_carbon_fiber \
  --plan-only
```

Execute:

```bash
python scripts/run_tavily_web_signal_search.py \
  --topic "PAN carbon fiber mid-temperature carbonization" \
  --categories national_project money ir_disclosure company local_news \
  --output-dir outputs/web_signals/tavily_pan_carbon_fiber \
  --max-queries 10 \
  --max-results-per-query 5 \
  --execute-tavily
```

## 出力ファイルの見方

```
outputs/web_signals/{batch_id}/
  web_signal_queries.json    # 検索計画
  tavily_search_raw.json     # Search API 生レスポンス（execute 時）
  tavily_extract_raw.json    # Extract API 生レスポンス（extract 時）
  web_signals.json
  web_signals.csv
  web_signal_summary.md
```

`web_signal_summary.md` には以下を明記します。

- Web signals are signal candidates, not final conclusions.
- IR / disclosure signals require document-level verification.
- Human signals require careful identity verification.
- Money / national_project signals require source verification.
- This is not FTO, infringement, or validity analysis.
- Synthetic demo signal must be clearly labeled.
- Tavily results are retrieved web candidates and may include noise.

## 注意事項

- Web signals are **candidates** — 断定しない
- IR 情報は **書類レベルの検証** が必須
- Human signal は **身元確認** が必須（low / medium から開始）
- 金額はユーザー向け UI に表示しない
- Synthetic demo signal は必ずラベル付けする
- FTO / 侵害 / 有効性判断はしない
- 自動スクレイピング・大規模クロールはしない

## 関連モジュール

- `src/tech_cartography/web_signals/tavily_adapter.py`
- `src/tech_cartography/web_signals/query_templates.py`
- `src/tech_cartography/web_signals/signal_classifier.py`
- `src/tech_cartography/web_signals/tavily_runner.py`
- `src/tech_cartography/web_signals/review_pack.py`（Phase 23.2）
- `scripts/run_tavily_web_signal_search.py`

## Phase 23.2 Review Pack への接続

Phase 23.2 では Tavily batch 生成後に **Web Signal Review Pack** を構築できます。

```bash
python scripts/run_tavily_web_signal_search.py \
  --topic "PAN carbon fiber mid-temperature carbonization" \
  --categories national_project money ir_disclosure company local_news \
  --output-dir outputs/web_signals/tavily_pan_carbon_fiber \
  --plan-only \
  --build-review-pack
```

詳細: `docs/phase23_web_signal_review_pack.md`

### --build-review-pack の使い方

- `--build-review-pack` を付けると `outputs/web_signals/{batch_id}/review_pack/` を生成
- plan-only で `signal_count=0` でも空の review pack を安全に作成
- `--review-min-priority` で高優先度フィルタの閾値を指定
- `--review-keywords` で evidence 抽出キーワードを上書き
- `--save-rejected` で低品質候補を `rejected_or_low_quality_sources.csv` に保存

### --extract-top-urls の注意

- execute 時のみ有効
- 追加 API 呼び出しが発生するため `--max-extract-urls` は **10 以下** に制限
- Extract 結果も signal candidate として扱い、本文確認は必須

### execute-tavily 時の安全上限

| パラメータ | 推奨 / 上限 |
|-----------|-------------|
| `--max-queries` | 10 以下（runner が自動制限） |
| `--max-results-per-query` | 5 以下 |
| `--max-extract-urls` | 10 以下 |
| `--categories` | `human` は除外 |

API キーは環境変数 `TAVILY_API_KEY` のみ。ログ・出力ファイルに含めません。
