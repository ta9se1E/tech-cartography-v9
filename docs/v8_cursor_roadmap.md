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

## Phase27B.1: Streamlit width 移行

**目的:** deprecated `use_container_width` を `width="stretch"` / `width="content"` へ置換し、ローカル起動警告を解消する。

**状態:** ✅ 完了（Phase27C 前の UI 警告解消）

**対象:** `app.py`, `src/tech_cartography/ui/`（v8 + v7 由来）、`easy_japanese_ui.py`

**完了条件:**
- `app.py` / `src` / `tests` に `use_container_width=` が残らない
- `check_v8_reframe_ready.py` が `Streamlit width migration: yes` を表示

**Cloud Build:** 不要

---

## Phase27C: Sources一覧 + Export

**目的:** 3案件の source_candidates と統合 schema で Sources 一覧・Export Package を本格化。

**状態:** ✅ 完了

**追加/修正:**
- `runtime/v8_sources_schema.py` — V8SourceRecord / V8SourcesTable / V8SourceExportPackage
- `services/v8_sources_loader.py`, `v8_sources_repository.py`, `v8_export_package.py`
- `ui/v8_sources_ui.py`, `ui/v8_export_ui.py` 本格化
- `cases/*/source_candidates.csv` 充実（各case patent 5+）

**完了条件:**
- 3案件 Sources 読込・フィルタ・CSV/MD/Excel/Package export
- Web/company = candidate information only
- 定点観測・メール Digest 引き継ぎ note を Export に含む

**Cloud Build:** 不要

---

## Phase27D: 読むべき特許 Top N

**目的:** Unified Sources から案件ごとに「読むべき特許 Top N」を heuristic で選定。

**追加/修正ファイル:**
- `src/tech_cartography/runtime/v8_patent_shortlist_schema.py`
- `src/tech_cartography/services/v8_patent_shortlist.py`
- `src/tech_cartography/services/v8_patent_shortlist_export.py`
- `src/tech_cartography/ui/v8_patent_shortlist_ui.py`
- `tests/test_v8_patent_shortlist_*.py`

**状態:** ✅ 完了

**完了条件:**
- 3案件それぞれ Top5（最低 Top3）の patent candidates
- why_read / next_verification_action / score_breakdown あり
- スコアは読む優先度の暫定値（FTO/侵害/有効性/法的判断ではない）
- claim text not loaded 明記
- Export: csv / md / xlsx / manifest
- Claim Map（Phase27E）へ接続

**定点観測:** Top 特許の変化を次回 Digest で追跡する方針

**Cloud Build:** 不要

---

## Phase27E: Claim Map v1

**目的:** Patent Shortlist 候補の請求項を技術軸へ整理する Claim Map v1。

**追加/修正ファイル:**
- `src/tech_cartography/runtime/v8_claim_map_schema.py`
- `src/tech_cartography/services/v8_claim_input_loader.py`
- `src/tech_cartography/services/v8_claim_map.py`
- `src/tech_cartography/services/v8_claim_map_export.py`
- `cases/*/claims_input.csv`

**状態:** ✅ 完了

**完了条件:**
- 3案件で Claim Map 生成（claims_input.csv 最低3件）
- claim text not loaded 明示
- evidence_needed / next_evidence_check
- Export: csv / md / xlsx / manifest

**Cloud Build:** 不要

---

## Phase27F: Evidence Map v2

**目的:** Claim Map と Unified Sources の裏付け候補対応表。

**追加/修正ファイル:**
- `src/tech_cartography/runtime/v8_evidence_map_schema.py`
- `src/tech_cartography/services/v8_evidence_map.py`
- `src/tech_cartography/services/v8_evidence_map_export.py`

**状態:** ✅ 完了

**完了条件:**
- 3案件で Evidence Map 生成
- supporting evidence candidate / not proof 明記
- claim_text_required 対応

**Cloud Build:** 不要

---

## Phase27G: Gap / Next Actions v2

**目的:** Evidence Map の不足情報を集約し、Top 3 Next Actions / Watch Profile update proposal / digest summary を生成する。

**追加/修正ファイル候補:**
- `src/tech_cartography/runtime/v8_gap_next_actions_schema.py`
- `src/tech_cartography/services/v8_gap_next_actions.py`
- `src/tech_cartography/services/v8_gap_next_actions_export.py`
- `src/tech_cartography/ui/v8_gap_next_actions_ui.py`
- Evidence Map / 定点観測 / Export UI 連携

**完了条件:**
- 3案件で Gap / Next Actions report を生成し Top 3 Actions を出力
- Gap は未確認事項（invalidity / weakness / infringement ではない）を明示
- Next Action は人間の確認作業（法的判断ではない）を明示
- Watch Profile update proposal / digest summary / scheduler follow-up / email digest hint を含む
- メール送信・Scheduler は必須機能として残す（本 Phase では送信・起動しない）
- 外部 API / LLM / Web 検索を呼ばない

**テスト観点:** schema JSON serializable、3案件生成、export csv/md/manifest、UI import

**Cloud Build:** 不要

---

## Phase27G-old: 定点観測ループ再配置（Phase27B 骨格）

**注:** Watch / Scheduler / Digest / Run History の UI 骨格は Phase27B で先行実装済み。Gap / Next Actions v2 は上記 Phase27G を参照。

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
