# v8 Three Case Validation Plan

## 目的

v8 の Claim / Evidence / Gap / 定点観測ループを、**3つの実案件**でローカル検証し、ハッカソン提出・実利用に耐える分析品質を詰める。

## 共通ルール

- **実データのみ**（特許公報番号・DOI・一次 URL）
- **架空情報禁止**
- Web Signal = **候補情報**（`candidate_information_only`）
- FTO / 侵害 / 有効性 / 法的判断 **禁止**
- 各出力に **source url** と **artifact path** を残す
- メール送信・Scheduler は **必須機能として残す**（デフォルト OFF、ループ説明は必須）

## Phase27C: source_candidates.csv

- 各 case の `cases/<case_id>/source_candidates.csv` を Unified Sources の入力とする
- 各 case **patent 5件以上**、paper 2件以上、web/company 候補 1件以上
- `v8_sources_loader` が CSV → `V8SourceRecord` に正規化
- Export Package は `outputs/local_v8_export_packages/` に保存
- Cloud Build はこの Phase では不要

## Phase27D: Patent Shortlist Top N

- `v8_patent_shortlist` が各 case の patent source から Top5（テストは Top3 以上）を生成
- スコアは **読む優先度の暫定値**（heuristic / draft）— 特許価値・権利価値・有効性判断ではない
- 3案件検証では各 case Top5 を人手で why_read / next_verification_action と照合
- 次 Phase: Claim Map で請求項を分解
- 定点観測: Top 特許リストの差分を次回 Digest に載せる

## Phase27E: Claim Map v1

- `cases/<case_id>/claims_input.csv` — Top 候補 publication_number（claim text は空欄可）
- Claim Map は技術整理であり法的解釈ではない
- claim text not loaded を UI / Export で明示
- 3案件で Claim Map を生成し、Evidence Map（Phase27F）へ接続
- 定点観測: Claim Map 軸の変化を次回 Digest で追跡

## Phase27F: Evidence Map v2

- Claim Map + Unified Sources から Evidence Map を生成
- supporting evidence candidate — 証明ではない
- claim text required / missing evidence を明示
- 3案件で Evidence Map 生成 → Gap / Next Actions（Phase27G）へ接続
- 定点観測: Evidence Gap 変化を次回 Digest で追跡

## Phase27G: Gap / Next Actions v2

- Evidence Map の不足を集約し Top 3 Next Actions を生成
- Gap は未確認事項（弱点・無効性・侵害可能性ではない）
- Next Action は人間の確認作業（法的判断ではない）
- Watch Profile update proposal / digest summary へ接続
- メール送信と Scheduler は必須機能として残す（本 Phase では送信・起動しない）
- 3案件で Top 3 Next Actions を出力

## Phase27H: Fixed Point Observation Loop

**目的:** Gap / Next Actions から Watch Profile / Scheduler / Email Digest 計画へ接続し、定点観測ループ artifact を生成する。

**追加/修正ファイル候補:**
- `src/tech_cartography/runtime/v8_fixed_point_observation_schema.py`
- `src/tech_cartography/services/v8_fixed_point_observation.py`
- `src/tech_cartography/services/v8_fixed_point_observation_export.py`
- `src/tech_cartography/ui/v8_fixed_point_observation_ui.py`

**完了条件:**
- 3案件で Observation Loop report を生成
- Watch Profile update proposal / Scheduler plan / Email digest plan を含む
- no_email_send / no_scheduler_start を明示
- メール送信・Scheduler は必須機能として残す
- Watch Profile 自動更新しない

**Cloud Build:** 不要

## Phase27I: Three Case Local Validation Pack

**目的:** 3案件それぞれについて v8 の一連の流れがローカルで成立しているか検証し、Cloud 反映前の検証パックを作成する。

**追加/修正ファイル:**
- `src/tech_cartography/runtime/v8_case_validation_schema.py`
- `src/tech_cartography/services/v8_case_validation_pack.py`
- `src/tech_cartography/services/v8_case_validation_export.py`
- `scripts/run_v8_three_case_validation_pack.py`

**各案件で確認する流れ:**

| # | step | 確認内容 |
|---|------|----------|
| 1 | Sources一覧 | source_candidates.csv、patent 5件以上、fake URL なし |
| 2 | 読むべき特許 Top N | Top3以上、why_read / next_verification_action |
| 3 | Claim Map | claims_input.csv、not_loaded 明示、架空 claim なし |
| 4 | Evidence Map | candidate 扱い、claim_text_required、not proof |
| 5 | Gap / Next Actions | Top 3、Gap は未確認事項 |
| 6 | 定点観測ループ | Watch Profile / Scheduler / Email 計画（実行しない） |
| 7 | Export | artifact path 収集、secret なし |

**readiness_for_demo 判定:**

| 値 | 意味 |
|----|------|
| `ready` | 一連の artifact がありデモ説明可能 |
| `needs_claim_text` | 流れは通るが claim 本文未取得が主要 blocking |
| `needs_more_sources` | Sources が不足 |
| `needs_manual_review` | human_review が多い |
| `not_ready` | 主要 step が生成できない |

**現状:** `claims_input.csv` の claim_text は空欄のため、3案件とも `needs_claim_text` になるのが正しい評価。

**Validation Pack 出力:** `outputs/local_v8_case_validation_packs/three_case_pack_*/`

- three_case_validation_pack.json / .md / .xlsx
- three_case_validation_manifest.json
- case_01〜03_validation_report.md
- demo_readiness_summary.md / cloud_readiness_summary.md

**Cloud Build:** 不要（Phase27L で反映準備）

**次 Phase 候補:**
- Phase27J — Manual Claim Injection（ユーザー提供 claim 本文の手動投入）✅
- Phase27J.0 — Large Candidate Import and 1000-scale Shortlisting ✅
- Phase27J.1 — Large Candidate UI polish
- Phase27K — Manual Claim Injection（継続）
- Phase27L — Evidence Map / Gap Demo Polish
- Phase27M — Cloud Run v8 反映準備

## Phase27J.0: Large Candidate Import and 1000-scale Shortlisting

**目的:** 各 Case 最大1000件の実在特許候補を CSV/Excel から取り込み、母集団として段階選抜する。

**重要:**
- 1000件は **母集団** — 全件 Deep Dive しない
- Top100 → Top20 → Top5 の段階選抜
- Claim Map / Evidence Map は Top5 またはユーザー選択に限定
- BigQuery はこの Phase では **実行しない** — 抽出済み CSV を UI/CLI で取り込む
- fake patent / fake DOI / fake URL を作らない
- cases/ 配下に架空1000件 CSV を入れない

**入力フォルダ:** `cases/<case_id>/large_candidates/README.md` を参照

**BigQuery SQL テンプレート:** `docs/bigquery_templates/case_*_1000.sql`（参考のみ、課金・dry-run 確認が必要）

**CLI:**
```bash
conda run -n 2026hack python scripts/run_v8_large_candidate_import.py \
  --case-id case_01_pan_graphitization \
  --input cases/case_01_pan_graphitization/large_candidates/case_01_bigquery_export_1000.csv \
  --max-rows 1000

conda run -n 2026hack python scripts/run_v8_large_candidate_shortlist.py \
  --case-id case_01_pan_graphitization
```

**Cloud Build:** 不要

## Phase27J.1: Ranking Explanation and Patent Triage Adapter

- 既存 `patent_triage.py` を再利用（存在しない場合は fallback heuristic）
- Top100/Top20/Top5 の選抜理由・スコア内訳を ranking explanation として出力
- score は読む優先度であり、技術的正しさ・特許価値・法的価値ではない
- 1000件全件 Deep Dive しない

**次 Phase:** Phase27N（Cloud Run）

## Phase27M: Final UI Demo Flow & Readiness

- Demo Readiness — artifact missing vs true zero
- 最短デモ操作 / ステップガイド / Sidebar Phase27M
- `scripts/run_v8_demo_readiness_check.py`
- Cloud Build / Cloud Run deploy はこの Phase では実行しない

## Phase27L: Evidence Map / Gap Demo Polish

- Evidence Map is not proof — supporting evidence candidate のみ
- Gap is not invalidity / weakness — 未確認事項
- claim 投入済み → Evidence Map 具体化（candidate 扱いは維持）
- Demo Polish Pack: `scripts/run_v8_demo_polish_pack.py`
- はじめにタブ: 推奨デモ操作手順

## Phase27K: Manual Claim Injection and Refresh

- Top5 から claim 投入対象を選択
- claim 本文はユーザー提供のみ（40文字未満 / placeholder は拒否）
- 投入後 Claim Map / Evidence Map / Gap / 定点観測を再生成
- claim_text_required_count が減ることを確認
- paper/web/company は candidate 扱いを維持

## Phase27J: Manual Claim Injection

**目的:** 各 Case で少なくとも 1 件、実 claim 本文を安全に手動投入し、Claim Map / Evidence Map / Gap / 定点観測を再生成する。

**重要:**
- claim 本文は **ユーザー提供のみ**（Google Patents / BigQuery / PDF / 手元資料からコピー）
- システムは claim 本文を **生成しない**
- `cases/` 配下に架空 claim を入れない
- `tests/fixtures/` のみ toy claim 可（`test fixture only, not real patent claim`）

**workbench:** `cases/<case_id>/manual_claim_workbench.md`

**CLI:**
```bash
conda run -n 2026hack python scripts/run_v8_manual_claim_refresh.py \
  --case-id case_01_pan_graphitization \
  --publication-number US5176959 \
  --claim-no 1
```

**Cloud Build:** 不要

## Case 1: PAN 系炭素繊維の前駆体・炭化・黒鉛化

| 項目 | 内容 |
|------|------|
| case_id | `case_01_pan_graphitization` |
| case_name | PAN系炭素繊維の前駆体・炭化・黒鉏化 |
| 焦点 | 前駆体、耐炎化、炭化、黒鉛化、強度・弾性率 |
| 検証軸 | process-property の裏取り |

## Case 2: サイジング・表面処理・界面・複合材料

| 項目 | 内容 |
|------|------|
| case_id | `case_02_sizing_interface` |
| case_name | サイジング・表面処理・界面・複合材料 |
| 焦点 | sizing、surface treatment、interface、matrix adhesion |
| 検証軸 | Claim と論文 Evidence の対応 |

## Case 3: CFRP 圧力容器・フィラメントワインディング・水素タンク

| 項目 | 内容 |
|------|------|
| case_id | `case_03_pressure_vessel_filament_winding` |
| case_name | CFRP圧力容器・フィラメントワインディング・水素タンク |
| 焦点 | 材料、成形、FW、強度、安全性、事業性 |
| 検証軸 | 高次加工材料としての Claim-Evidence-Gap |

## 各案件で必ず確認する出力

| # | 出力 | 合格の目安 |
|---|------|-----------|
| 1 | Sources一覧 | type / url / publication_number / artifact path |
| 2 | 読むべき特許 Top 5 | 請求項読了優先順位と理由 |
| 3 | Claim Map | claim 単位または patent 単位の主張構造 |
| 4 | Evidence Map | Claim ↔ Evidence 対応（論文・実施例・Web 候補） |
| 5 | Evidence Gap | 未確認・不足証拠の構造化 |
| 6 | Next Verification Actions | **3件**、owner / 一次情報 URL |
| 7 | 定点観測の次回検索範囲変更案 | Watch Profile 更新案 |
| 8 | Export | json/md/csv 等、案件フォルダへ保存 |

## 各案件の合格条件

- [ ] 実データを使用（`source_candidates.csv` の url / publication_number が検証可能）
- [ ] 架空情報なし
- [ ] source url / artifact path が全主要出力に残る
- [ ] claim または patent 単位で根拠が追える
- [ ] Web Signal は候補ラベル付き
- [ ] FTO / 侵害 / 有効性判断の文言なし
- [ ] 次に人間が確認すべき一次情報が明確
- [ ] メール Digest と Scheduler への接続が `validation_checklist.md` で説明できる
- [ ] `scripts/check_v8_reframe_ready.py` と案件テストが通る

## 検証フロー（Phase27H 想定）

1. `cases/<case_id>/` の seed を読み込む
2. ローカルで Sources → 特許 Top 5 → Claim/Evidence Map → Gap/Actions を生成
3. Watch Profile 更新案 → Scheduler dry-run → Digest Preview を確認
4. Export を `outputs/cases/<case_id>/` に保存
5. `validation_checklist.md` を人手でチェック

## ディレクトリ

```
cases/
  case_01_pan_graphitization/
  case_02_sizing_interface/
  case_03_pressure_vessel_filament_winding/
```
