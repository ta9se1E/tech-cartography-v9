# v8 User Flow and Tabs

## Phase27B 実装状況（UI骨格）

| タブ | モジュール | 状態 |
|------|-----------|------|
| はじめに | `v8_intro_ui.py` | ✅ 説明・フロー |
| 入力 | `v8_input_ui.py` | ✅ session_state 保存 |
| Sources一覧 | `v8_sources_ui.py` + `v8_sources_repository.py` | ✅ Unified Sources + Export |
| 読むべき特許 | `v8_patent_shortlist_ui.py` + `v8_patent_shortlist.py` | ✅ Top N heuristic |
| Claim Map | `v8_claim_map_ui.py` + `v8_claim_map.py` | ✅ Claim Map v1 |
| Evidence Map | `v8_evidence_map_ui.py` + `v8_evidence_map.py` | ✅ Evidence Map v2 |
| Gap / Next Actions | `v8_gap_next_actions_ui.py` | ✅ 既存 artifact 閲覧 |
| 定点観測 | `v8_fixed_point_observation_ui.py` | ✅ ループ説明 + 導線 |
| Export | `v8_export_ui.py` | ✅ CSV/MD/Excel/Package |
| 管理者設定 | `v8_admin_settings_ui.py` | ✅ 運用 UI 隔離 |

## Phase27C（Unified Sources + Export Package）

- schema: `V8SourceRecord` / `V8SourcesTable` / `V8SourceExportPackage`
- 3案件 `source_candidates.csv` を統合読込（各 case patent 5+）
- フィルタ: case / source_type / evidence_role / verification / candidate_only / 検索
- ダウンロード: CSV / Markdown / Excel / Export Package（manifest + summary）
- Web/company = candidate information only
- Sources は Patent Shortlist / Claim Map / Evidence Map の基礎データ
- Export に定点観測・メール Digest 引き継ぎ note を含む

## Phase27D（読むべき特許 Top N）

- schema: `V8PatentCandidate` / `V8PatentShortlist` / `V8PatentShortlistExport`
- Unified Sources の `source_type=patent` から案件ごとに Top N（3 / 5 / 10）を heuristic スコアリング
- **total_score = 読む優先度の暫定スコア**（特許価値・権利価値・有効性・法的判断ではない）
- claim text not loaded — 請求項・明細書は未読であることを常時明記
- Export: `outputs/local_v8_patent_shortlists/` に csv / md / xlsx / manifest
- 次 Phase: **Claim Map**（請求項分解）→ Evidence Map → Gap / Next Actions
- 定点観測ループ: Top 特許の変化を次回 Digest / Scheduler で追跡する方針

## Phase27E（Claim Map v1）

- schema: `V8ClaimRecord` / `V8ClaimMap` / `V8ClaimMapExport`
- Patent Shortlist Top 候補 + `cases/<case_id>/claims_input.csv` / 手動 claim text から Claim Map を生成
- **Claim Map は技術整理の暫定分類** — 権利範囲解釈・FTO/侵害/有効性判断ではない
- claim text not loaded — 本文未取得時は `not_loaded` と明示し、内容を推測しない
- ルールベースで technical_axis / material / process / property / evidence_needed を抽出
- Export: `outputs/local_v8_claim_maps/` に csv / md / xlsx / manifest
- 次 Phase: **Evidence Map**（実施例・論文対応）→ Gap / Next Actions
- 定点観測: Claim Map 軸の変化を次回 Digest で追跡する方針

## Phase27F（Evidence Map v2）

- schema: `V8EvidenceLink` / `V8EvidenceMap` / `V8EvidenceMapExport`
- Claim Map の technical_axis / evidence_needed と Unified Sources をルールベースで対応付け
- **supporting evidence candidate** — 証明・確定 Evidence ではない（Evidence Map is not proof）
- claim text not loaded → `claim_text_required` / missing
- paper → `paper_support_candidate`（medium_candidate）、web/company → weak_candidate + needs_human_review
- Export: `outputs/local_v8_evidence_maps/` に csv / md / xlsx / manifest
- 次 Phase: **Gap / Next Actions** — 定点観測 Digest で Evidence Gap 変化を追跡

- エントリポイント: `app.py` → `render_v8_user_flow_app`（`APP_UI_VERSION` 未設定時 v8）
- v7 UI は削除せず `APP_UI_VERSION=v7` で切替
- メール送信・Scheduler は削除せず、定点観測タブで必須機能として説明、詳細は管理者設定へ

## 設計方針

- ユーザー向け主役: **Sources → 読むべき特許 → Claim → Evidence → Gap/Actions → 定点観測 → Export**
- 管理者情報（IAP/SMTP/Scheduler 詳細）は **タブ10** に隔離
- **メール送信** と **Scheduler** は定点観測の必須機能（デフォルト OFF、UI ではループ説明を前面に）
- **Watch Profile / Scope Feedback / Run History** は定点観測タブに集約

## 推奨タブ一覧

| # | タブ名 | 主役 |
|---|--------|------|
| 1 | はじめに | 案件概要・使い方 |
| 2 | 入力 | キーワード・案件選択 |
| 3 | Sources一覧 | 出典と artifact |
| 4 | 読むべき特許 | Top N 優先順位 |
| 5 | Claim Map | 請求項・主張構造 |
| 6 | Evidence Map | Claim-Evidence 対応 |
| 7 | Gap / Next Actions | Gap + 次の確認 |
| 8 | 定点観測 | Watch / Scheduler / Digest |
| 9 | Export | 成果物ダウンロード |
| 10 | 管理者設定 | IAP/SMTP/運用（裏方） |

---

## 1. はじめに

**目的:** 案件のテーマと v8 の価値（Claim-Evidence-Gap-定点観測）を説明する。

**ユーザーが見る情報:**
- case_name / theme
- やらないこと（FTO/侵害/有効性/法的結論）
- タブの読み順ガイド

**ユーザーが押すボタン:**
- 「案件を選ぶ」→ 入力タブ
- 「3案件サンプルを見る」

**使う既存機能:** case profile 読み込み、既存 analyst モード切替

**新規に必要な機能:** v8 ウェルカムパネル、case セレクタ

**表示してはいけない管理者情報:** IAP URL、SMTP パスワード、Cloud Run revision

**出力 artifact:** なし

**次のタブへの導線:** → 入力

---

## 2. 入力

**目的:** seed keywords / queries / patent ids を投入し分析 run を開始する。

**ユーザーが見る情報:**
- seed_keywords, seed_queries, seed_patent_ids（case_profile から）
- exclusion_keywords

**ユーザーが押すボタン:**
- 「分析を開始」
- 「case_profile を読み込む」

**使う既存機能:** 既存パイプライン入力、Watch Profile draft 作成

**新規に必要な機能:** `cases/*/case_profile.yaml` ローダー

**表示してはいけない管理者情報:** API secret 値、Scheduler cron 生値

**出力 artifact:** `run_manifest.json`

**次のタブへの導線:** run 完了後 → Sources一覧

---

## 3. Sources一覧

**目的:** 特許・論文・Web の出典を一覧し、追跡可能にする。

**ユーザーが見る情報:**
- type, title, organization, year, url, publication_number
- source_status, evidence_role
- artifact path

**ユーザーが押すボタン:**
- 「CSV エクスポート」
- 「source を Evidence Map へ」

**使う既存機能:** live artifact paths、既存 patent/paper 収集

**新規に必要な機能:** Sources 統合テーブル UI、`source_candidates.csv` マージ

**表示してはいけない管理者情報:** GCS bucket 内部パス詳細（ユーザー向けは相対 artifact path のみ）

**出力 artifact:** `sources_index.json`, `sources_index.csv`

**次のタブへの導線:** → 読むべき特許

---

## 4. 読むべき特許

**目的:** 請求項・実施例を読む優先順位 Top N を提示する。

**ユーザーが見る情報:**
- Top 5: publication_number, title, read_priority_reason, claim_focus
- 各 patent の url / artifact path

**ユーザーが押すボタン:**
- 「Claim Map へ」
- 「Google Patents で開く」

**使う既存機能:** 既存 patent ranking、Evidence Gap 連携

**新規に必要な機能:** Top N ランキングサービス v1

**表示してはいけない管理者情報:** 外部 API クォータ

**出力 artifact:** `top_patents.json`

**次のタブへの導線:** → Claim Map

---

## 5. Claim Map

**目的:** 請求項・技術主張を構造化して見せる。

**ユーザーが見る情報:**
- claim 軸（case_profile.expected_claim_axes）
- patent / claim 単位の主張テキスト要約
- 根拠 publication_number

**ユーザーが押すボタン:**
- 「Evidence Map へ」
- 「Gap を確認」

**使う既存機能:** 既存 claim 抽出（あれば）、Strategic Watch Brief 参照

**新規に必要な機能:** Claim Map v1 ビュー

**表示してはいけない管理者情報:** LLM プロンプト全文

**出力 artifact:** `claim_map.json`

**次のタブへの導線:** → Evidence Map

---

## 6. Evidence Map

**目的:** Claim と Evidence（論文・実施例・Web 候補）の対応を示す。

**ユーザーが見る情報:**
- claim_id ↔ evidence_id マトリクス
- Web Signal 行は `candidate_information_only` バッジ

**ユーザーが押すボタン:**
- 「Gap を見る」
- 「一次 URL を開く」

**使う既存機能:** Evidence Map 既存実装、Web Signal pack

**新規に必要な機能:** v2 統合ビュー（Sources 連携）

**表示してはいけない管理者情報:** Tavily raw response

**出力 artifact:** `evidence_map.json`

**次のタブへの導線:** → Gap / Next Actions

---

## 7. Gap / Next Actions

**目的:** 裏取り不足と人間が次に見る一次情報を明示する。

**ユーザーが見る情報:**
- Evidence Gap リスト
- Next Verification Actions（3件）
- 各 action の primary_source url

**ユーザーが押すボタン:**
- 「定点観測へ反映」
- 「Export」

**使う既存機能:** Evidence Gap service、Strategic Watch Brief

**新規に必要な機能:** Next Actions 固定3件フォーマット

**表示してはいけない管理者情報:** 法的リスクスコア

**出力 artifact:** `evidence_gap.json`, `next_actions.json`

**次のタブへの導線:** → 定点観測

---

## 8. 定点観測（必須要素）

**目的:** Watch Profile 更新と Scheduler・メール Digest による定点観測ループを操作・説明する。

**ユーザーが見る情報（すべて必須）:**
1. **Watch Profile** — active keywords / patent ids
2. **検索範囲の拡張** — Scope Expansion 提案
3. **検索範囲の縮小** — ノイズ除外提案
4. **検索範囲の重点化** — focus keywords
5. **除外キーワード** — exclusion_keywords
6. **次回 Scheduler 実行** — 予定時刻（dry-run 可）
7. **メール Digest 送信** — Digest Preview リンク
8. **前回との差分** — new patents / gap delta
9. **Run History** — 直近 run 一覧
10. **Scope Feedback** — ユーザーフィードバック入力

**ユーザーが押すボタン:**
- 「Watch Profile を更新」
- 「Scheduler dry-run」
- 「Digest Preview」
- 「Scope Feedback を送信」

**使う既存機能:**
- Watch Profile management
- Scheduler config（デフォルト OFF）
- メール送信 / Digest Preview
- Run History
- Scope Expansion / Feedback

**新規に必要な機能:** 定点観測統合パネル、case 別 watch delta 表示

**表示してはいけない管理者情報:** SMTP パスワード、Cloud Scheduler job 名の生値、IAP client secret

**出力 artifact:** `watch_profile_delta.json`, `fixed_point_observation_plan.json`

**次のタブへの導線:** → Export

---

## 9. Export

**目的:** 案件検証成果物を一括ダウンロードする。

**ユーザーが見る情報:**
- 出力ファイル一覧と生成日時
- checksum / artifact path

**ユーザーが押すボタン:**
- 「ZIP ダウンロード」
- 「validation_checklist 用 PDF」

**使う既存機能:** live artifact export、既存 json/md 出力

**新規に必要な機能:** case 単位バンドル export

**表示してはいけない管理者情報:** サービスアカウント鍵

**出力 artifact:** `outputs/cases/<case_id>/` 一式

**次のタブへの導線:** → はじめに（別案件）または 定点観測（次週）

---

## 10. 管理者設定

**目的:** 運用・認証・送信の設定（ユーザー主役から隔離）。

**ユーザーが見る情報:**
- IAP / SMTP / Scheduler の **状態サマリー** のみ
- Operation Status

**ユーザーが押すボタン:**
- 「接続テスト」（管理者のみ）

**使う既存機能:** 既存 admin タブ群を集約

**新規に必要な機能:** analyst モードからの分離リダイレクト

**表示してはいけない管理者情報:** （一般ユーザーにはタブ自体非表示）

**出力 artifact:** なし

**次のタブへの導線:** —
