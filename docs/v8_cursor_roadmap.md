# v8 Cursor Implementation Roadmap

## 基本方針

- **Phase27B〜27H はローカル中心**（`README_v8_LOCAL_FIRST.md` 参照）
- **Cloud Build は大きな節目だけ**（Phase27I）。日常開発では必須にしない
- 既存 v7 機能を壊さない（メール / Scheduler / Watch Profile / Run History は削除しない）
- 管理者機能はタブ10に隔離
- 3案件で納得できる品質になるまで Cloud 反映しない

---

## Phase27A: v8方針と3案件固定

**目的:** ドキュメント・case 定義・readiness check・テストで v8 の土台を固定する。

**追加/修正ファイル候補:**
- `docs/v8_product_reframe.md`
- `docs/v8_three_case_validation_plan.md`
- `docs/v8_user_flow_and_tabs.md`
- `docs/v8_cursor_roadmap.md`
- `README_v8_LOCAL_FIRST.md`
- `cases/case_*/`（3案件）
- `scripts/check_v8_reframe_ready.py`
- `tests/test_v8_*.py`

**完了条件:**
- readiness check PASS
- pytest 全件 PASS
- 3 case_profile.yaml が読める

**テスト観点:** ドキュメント存在、case CSV 列、必須キーワード記載

**Cloud Build:** 不要

---

## Phase27B: UI再配置

**目的:** analyst モードのタブを v8 10タブ構成に再配置。管理者設定を隔離。

**状態:** ✅ 完了（UI骨格 — 本格分析ロジックは Phase27C 以降）

**追加/修正ファイル:**
- `src/tech_cartography/ui/v8_user_flow_app.py`
- `src/tech_cartography/ui/v8_tab_config.py`
- `src/tech_cartography/ui/v8_*_ui.py`（10タブ分）
- `src/tech_cartography/services/v8_sources_table.py`
- `app.py` — `APP_UI_VERSION=v8`（デフォルト）/ `v7` 切替
- `scripts/check_v8_reframe_ready.py` — Phase27B チェック追加
- `tests/test_v8_*.py`

**完了条件:**
- 10タブが `render_v8_user_flow_app` で表示
- 管理者タブは admin のみ詳細、member は最小表示
- user-facing タブに SMTP_PASSWORD / TAVILY_API_KEY なし
- メール送信・Scheduler は定点観測タブで必須機能として説明

**テスト観点:** タブ順序、import、Sources CSV 読取、安全ラベル

**Cloud Build:** 不要

---

## Phase27C: Sources一覧 + Export

**目的:** Sources 統合テーブルと case 単位 Export。

**追加/修正ファイル候補:**
- `src/tech_cartography/services/sources_index.py`
- `src/tech_cartography/ui/sources_index_ui.py`
- `cases/*/source_candidates.csv` ローダー

**完了条件:** 3案件で sources_index artifact が出る

**テスト観点:** url / publication_number / artifact path

**Cloud Build:** 不要

---

## Phase27D: 読むべき特許 Top N

**目的:** 請求項読了優先順位 Top 5。

**追加/修正ファイル候補:**
- `src/tech_cartography/services/top_patents_ranking.py`
- `tests/test_top_patents_ranking.py`

**完了条件:** case ごとに top_patents.json（最大5件）

**テスト観点:** 架空 patent なし、reason フィールドあり

**Cloud Build:** 不要

---

## Phase27E: Claim Map v1

**目的:** expected_claim_axes に沿った Claim Map。

**追加/修正ファイル候補:**
- `src/tech_cartography/services/claim_map_v1.py`
- UI コンポーネント

**完了条件:** claim_map.json が patent/claim 単位で追跡可能

**テスト観点:** publication_number 紐付け

**Cloud Build:** 不要

---

## Phase27F: Evidence Map v2

**目的:** Claim-Evidence 対応の統合。Web Signal は候補ラベル。

**追加/修正ファイル候補:**
- 既存 Evidence Map 拡張
- `evidence_map.json` スキーマ

**完了条件:** Web Signal 行に candidate_information_only

**テスト観点:** Gap 連携、fake evidence 禁止

**Cloud Build:** 不要

---

## Phase27G: 定点観測ループ再配置

**目的:** 定点観測タブに Watch / Scheduler / Digest / Run History / Scope Feedback を集約。

**追加/修正ファイル候補:**
- `src/tech_cartography/ui/fixed_point_observation_ui.py`
- Watch Profile delta サービス

**完了条件:**
- メール送信・Scheduler が必須機能として UI に説明される（デフォルト OFF）
- validation_checklist の定点観測項目を満たす

**テスト観点:** dry-run、Digest Preview リンク、Run History 記録

**Cloud Build:** 不要

---

## Phase27H: 3案件検証

**目的:** 3案件をローカルで end-to-end 検証し checklist を Pass。

**追加/修正ファイル候補:**
- `outputs/cases/` 成果物
- `docs/v8_three_case_validation_report.md`

**完了条件:** 3案件すべて validation_checklist Pass

**テスト観点:** 実データ、FTO 文言なし、Next Actions 3件

**Cloud Build:** 不要

---

## Phase27I: Cloud反映・提出準備

**目的:** ローカル品質確認後に Cloud Build / Cloud Run へ反映。

**追加/修正ファイル候補:**
- `cloudbuild.yaml`（必要時のみ）
- `docs/v8_submission_checklist.md`

**完了条件:** live smoke + IAP + artifact 永続化確認

**テスト観点:** `check_live_beta_ready.py`、本番 digest dry-run

**Cloud Build:** **必要**（この Phase のみ本番デプロイ節目）
