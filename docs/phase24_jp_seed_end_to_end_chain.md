# Phase 24.4C — JP Seed End-to-End Chain Completion

## 目的

Phase24.4A〜24.4B で確認した JP seed 3 件（Stage 3 pass）について、Streamlit UI 上から Evidence Map skeleton の後続工程を最後までつなげる。

**Manual Claims → Evidence Map skeleton → Paper候補 → Webシグナル候補 → Link Candidate → Strategic Watch → Digest**

## 対象 seed

- JP2022090764A
- JP2023163084A
- JP2018084002A

## Stage 4〜8 の意味

| Stage | 内容 | 出力先 |
|-------|------|--------|
| Stage 4 | Paper 候補（supporting evidence candidate） | `outputs/paper_candidates/{pub}/` |
| Stage 5 | Web シグナル候補（signal candidate） | `outputs/web_signals/{theme_id}_{pub}/` |
| Stage 6 | Link Candidate（確認候補、直接関係の証明ではない） | `outputs/web_signal_links/{pub}/` |
| Stage 7 | Strategic Watch Brief（監視候補） | `outputs/strategic_watch_briefs/{pub}/` |
| Stage 8/9 | JP Seed Digest（preview only、送信なし） | `outputs/delivery/jp_seed_digest_{pub}.md` |

## OpenAlex / Tavily / BigQuery 実行条件

- **デフォルト**: `dry_run=true`, `allow_external_api=false` → 外部 API **実行しない**
- **Paper Query Plan / Web Signal Query Plan のみ**生成
- **OpenAlex 実行**: `allow_external_api=true` **かつ** `run_openalex=true` **かつ** `dry_run=false`
- **Tavily 実行**: `allow_external_api=true` **かつ** `run_tavily=true` **かつ** `dry_run=false`
- **BigQuery**: 本 Phase では基本未使用（`run_bigquery=false` デフォルト）
- **TAVILY_API_KEY** 未設定時: `blocked_missing_tavily_config`（失敗扱いにしない）

### dry-run と external API 実行の違い

| モード | Paper | Web |
|--------|-------|-----|
| query_plan_only / allow_external_api=false | `paper_query_plan.json` のみ | `web_signal_query_plan.json` のみ |
| allow_external_api + run_* + dry_run=false | OpenAlex 実行 → CSV 保存 | Tavily 実行 → review_pack |

## 重要な注意（断定しない）

- **Paper候補**: supporting evidence candidate。特許請求項の証明ではない
- **Webシグナル**: signal candidate。money/national_project/IR は原典確認が必要
- **Link Candidate**: 確認候補。Phase23.4.1 calibrated scoring 使用。全件100点問題を回避
- **Strategic Watch**: 監視候補。Paper/Web 不足時は `limited_watch_brief`
- **Digest**: preview only。UI からメール送信しない
- **FTO / 侵害 / 有効性**: 法的判断ではない

## UI 操作手順

1. トップレベルタブ「**別テーマ検証**」を開く
2. テーマ名・theme_id・seed 3 件を入力
3. Seed 進捗で Stage 3 pass を確認
4. **JP Seed End-to-End Chain** セクションで publication numbers を選択
5. ボタンで各ステップを実行

### JP2022090764A から 1 件ずつ

1. End-to-End状態を確認する
2. Paper Query Planを作る
3. `allow_external_api=false` で Paper候補を取得 → query_plan のみ
4. `allow_external_api=true` + `run_openalex=true` + `dry_run=false` で Paper候補取得
5. Web Signal Query Planを作る
6. `allow_external_api=true` + `run_tavily=true` で Web Signal候補取得
7. Link Candidateを生成する
8. Strategic Watch Briefを生成する
9. Digest Previewを生成する
10. End-to-Endレポートを保存する

### 3 件まとめて

- publication numbers で 3 件を multiselect
- 「選択したseedの全ステップを実行する」で一括（外部 API は設定に従う）

## 失敗時の読み方

| status | 意味 |
|--------|------|
| `query_plan_ready` | 計画のみ保存済み。外部 API 未実行 |
| `external_api_required` | 次は allow_external_api で実行 |
| `blocked_missing_tavily_config` | TAVILY_API_KEY 未設定 |
| `blocked_missing_paper_or_web_signal` | Paper/Web の実データ不足で Link 不可 |
| `paper_link_missing` / `web_signal_missing` | 片方のみ query_plan |
| `limited_watch_brief` | Paper/Web 不完全でも監視候補のみ生成 |

## 出力レポート

`outputs/validation/end_to_end_chain/{theme_id}/`

- `end_to_end_chain_summary.md` / `.json`
- `seed_chain_status.csv`
- `next_actions.md`

## モジュール

- `src/tech_cartography/validation/end_to_end_chain.py`
- `src/tech_cartography/ui/theme_validation_ui.py` — `render_end_to_end_chain_section`
- `tests/test_end_to_end_chain.py`
- `tests/test_end_to_end_chain_ui.py`
