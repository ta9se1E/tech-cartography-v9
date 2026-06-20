# Phase 24.4A — User Theme Validation UI

## 目的

MVP Freeze 前に、炭素繊維以外の独自テーマでも Streamlit UI 上でキーワード入力・検索計画・既存 outputs 検証・停止理由確認ができるようにする。CLI だけでなく、ユーザーが UI で「別テーマでも動くか」を確認するためのコア価値検証 UI です。

## UIでできること

- テーマ名・説明・各種キーワード・seed publication numbers の入力
- 検索計画の dry-run（外部 API 未実行）
- 既存 `outputs/` のみを使った Stage 検証
- 明示同意後のみの特許候補外部検索（BigQuery 設定時）
- Manual Claims JSON テンプレート生成
- Stage Matrix 表示と検証レポート保存

**UI から行わないこと:** メール送信、scheduler 登録、外部 API の自動実行、FTO/侵害/有効性判断。

## 入力項目

| 項目 | 形式 |
|------|------|
| テーマ名 | text_input |
| テーマ説明 | text_area |
| コアキーワード | カンマ/改行区切り text_area |
| 用途キーワード | 同上 |
| 材料・プロセスキーワード | 同上 |
| 除外キーワード | 同上 |
| seed publication numbers | カンマ区切り（任意） |

## dry-run（ボタン A）

- 外部 API を叩かない
- キーワードを正規化し検索クエリ案を表示
- Stage 0–1 を `pass`、Stage 2 以降は `not_run`
- 「外部 API 未実行」を warnings に明記

## 既存 outputs 検証（ボタン B）

seed publication がある場合、以下を確認します。

- `outputs/manual_fulltext_inputs/{pub}.json`
- `outputs/evidence_map_synthesis/{pub}/evidence_map_synthesis.json`
- `outputs/openalex_limited_execution/selected_evidence_papers.csv`
- `outputs/web_signal_links/{pub}/web_signal_link_candidates.csv`
- `outputs/strategic_watch_briefs/{pub}/strategic_watch_brief.json`
- `outputs/delivery/weekly_digest_preview_{pub}.md`

存在すれば `pass`、なければ `output_missing` または `manual_input_required`。

## 外部検索実行時の注意（ボタン C）

- 実行前に警告を表示
- 「外部検索を実行することに同意します」チェック必須
- `max_patents` デフォルト 5
- BigQuery 未設定時は `external_search_not_configured`（`not_implemented` ではない）

## Manual Claims テンプレート（ボタン D）

seed publication 指定時に以下を生成します。

- `outputs/manual_fulltext_inputs/{publication_number}.template.json`
- `outputs/validation/theme_validation/{theme_id}/manual_claims_template_{publication_number}.json`

`claims_text` に Claims を貼り付け、`.json` として保存すると次段階に進めます。

## Stage Matrix の見方

| Stage | 名称 |
|------:|------|
| 0 | theme_config_loaded |
| 1 | search_plan_created |
| 2 | patent_candidates_available |
| 3 | fulltext_or_manual_claims_available |
| 4 | evidence_map_available_or_buildable |
| 5 | paper_candidates_available |
| 6 | web_signal_candidates_available |
| 7 | link_candidates_available |
| 8 | strategic_watch_available |
| 9 | digest_available |

status: `pass`, `blocked`, `not_run`, `manual_input_required`, `external_api_required`, `external_search_not_configured`, `output_missing`, `failed`

## 独自テーマでのテスト手順（Phase 24.4A.1 更新）

1. `streamlit run app.py` で起動
2. メールでログイン
3. トップレベルタブ **「別テーマ検証」** を開く（run_id 未読み込みでも表示されます）
4. **テーマ名** と **コアキーワード** を入力
5. **A. 検索計画を作成する（dry-run）** を押す → Stage Matrix と検索クエリ案を確認（外部 API 未実行）
6. **B. 既存outputsだけで検証する** を押す
   - seed なし: Stage 2 以降は `not_run` または `output_missing`
   - seed あり・成果物なし: `manual_input_required` / `output_missing` で停止理由を確認
7. seed を指定して **D. Manual Claimsテンプレートを作成する** → テンプレート JSON のパスを確認
8. **Manual Claims Editor** で claims_text を貼り付け **Manual Claimsを保存する**
9. **保存後に既存outputs検証を再実行する** → Stage 2 が `pass` になることを確認
10. **E. 検証レポートを保存する** → Manual Claims 状態が report に含まれることを確認

レポートタブには保存済みレポートへのリンクと保存先パスのみ表示します。入力・検証の主導線は **別テーマ検証** タブです。

## タブ構成

1. はじめる
2. 特許候補
3. 全文確認
4. 技術の裏取り
5. 企業・市場シグナル
6. **別テーマ検証**（入力・dry-run・検証の主画面）
7. レポート
8. 設定

## 旧手順（Phase 24.4A）

~~「レポート」タブでテーマ名・キーワードを入力~~ → 24.4A.1 以降は上記の **別テーマ検証** タブを使用してください。

## Manual Claims Editor（Phase 24.4A.2）

別テーマ検証タブ内の **Manual Claims入力 / Manual Claims Editor** で、公報原文からコピーした請求項を UI 上で保存できます。

### 使い方

1. seed publication numbers に対象特許を入力（例: `JP2022090764A, JP2023163084A, JP2018084002A`）
2. **D. Manual Claimsテンプレートを作成する**（任意）
3. **Manual Claims Editor** で publication number を選択し、`claims_text` に公報原文の請求項を貼り付け
4. **Manual Claimsを保存する** → `outputs/manual_fulltext_inputs/{publication_number}.json`
5. **保存後に既存outputs検証を再実行する** → Stage 2 が `pass` になることを確認
6. Stage 3 以降は `output_missing` のまま（Evidence Map 生成は別 Phase）

### 注意

- **AIでClaimsを作成・補完しない**（ユーザーが公報原文からコピーした本文のみ）
- claims_text が 200 文字未満の場合は警告（保存は可能）
- 既存ファイルがある場合は上書き確認チェックボックスが必要
- 本入力は FTO・侵害・有効性判断には使用しない

### theme_id の考え方

- 保存用テーマIDは編集可能（デフォルトはテーマ名＋キーワードから自動生成）
- 短すぎる ID（例: `pan`）は避ける — 複数テーマで衝突しやすい
- 推奨例: `pan_precursor_surface_internal_defects`
- 既存の `pan` フォルダは手動で theme_id を `pan` に指定すれば後方互換で読めます

### 今回の検証例

- theme_id: `pan_precursor_surface_internal_defects`
- seed: `JP2022090764A`, `JP2023163084A`, `JP2018084002A`

## 出力ファイル

`outputs/validation/theme_validation/{theme_id}/`

- `theme_validation_report.md`
- `theme_validation_result.json`
- `theme_validation_matrix.csv`
- `search_plan.json`
- `manual_claims_template_{publication_number}.json`（必要時）

## 既知制限

- UI 起動だけでは BigQuery / OpenAlex / Tavily は実行しない
- 論文・Web シグナルは確認候補であり法的結論ではない
- high confidence の自動付与はしない
- DB・Cloud Run・メール送信・scheduler 登録は本 Phase の対象外

## 関連ファイル

- `src/tech_cartography/ui/theme_validation_ui.py`
- `src/tech_cartography/validation/theme_validation.py`
- `docs/demo_script_phase21.md`（デモ台本に別テーマ検証セクションを追記可能）
