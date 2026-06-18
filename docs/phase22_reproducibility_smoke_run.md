# Phase 22.0 — Reproducibility Smoke Run

## 目的

US-12565719-B2 以外の特許候補について、Evidence Map パイプラインの**再現性**を診断します。

Phase 21.2 まででデモ UI は整いましたが、審査員や利用者からは次の問いが来やすくなります。

> 「これは1件だけの偶然ではないのか？」

Phase 22.0 は、この問いに答えるための **Reproducibility Smoke Run** です。  
新しい UI Polish は行わず、追加 1〜2 件の特許について「どこまで進めるか」を安全に記録します。

## なぜ再現性確認が必要か

- Evidence Map デモは US-12565719-B2 に最適化されている
- 他の Top 候補でも同じフロー（availability → manual route → query plan）が使えるかは未検証
- BigQuery fulltext / manual claims / OpenAlex の各段階で **blocked 理由** を明示する必要がある

## 実行コマンド

### Dry run（外部 API / BigQuery なし）

```bash
python scripts/run_reproducibility_smoke.py \
  --publication-numbers US-12565719-B2 US-12435451-B2 US-12516451-B2 \
  --dry-run
```

### Smoke run（BigQuery probe + 既存 manual claims 利用）

```bash
python scripts/run_reproducibility_smoke.py \
  --publication-numbers US-12565719-B2 US-12435451-B2 US-12516451-B2 \
  --output-dir outputs/reproducibility_smoke \
  --use-existing-manual-inputs \
  --build-query-plan-if-manual-exists
```

### OpenAlex 実行（必要な場合のみ・別確認後）

```bash
python scripts/run_reproducibility_smoke.py \
  --publication-numbers US-12435451-B2 \
  --output-dir outputs/reproducibility_smoke \
  --use-existing-manual-inputs \
  --build-query-plan-if-manual-exists \
  --execute-openalex
```

原則として OpenAlex 実行は別確認後に行ってください。デフォルトは **plan_only** です。

## CLI オプション一覧

| オプション | 説明 |
|-----------|------|
| `--publication-numbers` | 対象特許（複数可） |
| `--output-dir` | 出力先（既定: `outputs/reproducibility_smoke`） |
| `--max-patents` | 最大処理件数 |
| `--skip-bigquery` | BigQuery availability probe をスキップ |
| `--use-existing-manual-inputs` | `outputs/manual_fulltext_inputs` を参照 |
| `--build-query-plan-if-manual-exists` | manual claims がある場合のみ query plan 生成 |
| `--execute-openalex` | 明示時のみ OpenAlex 実行 |
| `--plan-only-openalex` | OpenAlex は計画のみ（デフォルト） |
| `--dry-run` | 実行予定のみ表示、外部 API なし |

## 出力ファイル

| ファイル | 内容 |
|---------|------|
| `reproducibility_summary.csv` | 特許ごとの診断サマリー |
| `reproducibility_summary.json` | 同上（JSON） |
| `reproducibility_summary.md` | 人間向けレポート |
| `next_manual_claims_checklist.md` | manual claims 追加手順 |

per-patent 成果物（query plan 等）は `{output_dir}/per_patent/{publication_number}/` に保存されます。

## status 一覧

| status | 意味 |
|--------|------|
| `complete_existing_demo` | US-12565719-B2 デモ成果物が揃っている |
| `evidence_map_ready` | Evidence Map 成果物が存在 |
| `openalex_plan_ready` | OpenAlex 実行計画まで作成済み |
| `query_plan_ready` | manual claims から query plan 生成済み |
| `manual_claims_available` | manual claims が存在 |
| `bigquery_fulltext_available` | BigQuery から claims/description 取得可能 |
| `manual_route_required` | Manual Claims Route が必要 |
| `blocked_missing_manual_claims` | manual claims がなく次に進めない |
| `blocked_cost_guard` | cost guard で probe 停止 |
| `error` | 想定外エラー（スクリプト全体は継続） |

## manual claims checklist の使い方

1. `next_manual_claims_checklist.md` を開く
2. `blocked_missing_manual_claims` の特許を確認
3. Google Patents URL 候補を**手動で**開き、claims を取得
4. `import_manual_fulltext.py` の例コマンドで `outputs/manual_fulltext_inputs` に保存
5. smoke run を再実行

自動スクレイピングは行いません。

## 注意事項

- **FTO、侵害、有効性判断ではない**
- 論文候補は **supporting evidence candidate**（証明ではない）
- **claims_only** / manual route の場合、confidence は最大 medium、基本 low/weak
- **架空情報を本物のように見せない**
- **ユーザー向けレポートに金額は出さない**
- 1 件失敗しても全体は止めない
- cost guard / not_found cache は既存設計を尊重

## 関連モジュール

- `scripts/run_reproducibility_smoke.py` — CLI エントリ
- `src/tech_cartography/validation/reproducibility_smoke.py` — 診断ロジック
- `scripts/check_fulltext_availability.py` — BigQuery probe（再利用）
- `scripts/build_claims_paper_query_plan.py` — query plan（再利用）
- `docs/demo_script_phase21.md` — デモ台本・Q&A
