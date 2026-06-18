# Phase 21 — Evidence Map デモモード UI ガイド

## Phase 21.2 の目的

Phase 21.1 で追加した US-12565719-B2 Evidence Map デモを、研究者・中小企業・ハッカソン審査員が **一目で価値を理解できる UI** に改善します。

- 新しい分析アルゴリズムは追加しない
- BigQuery / OpenAlex の新規実行は行わない
- 既存 `outputs/` を読み込み、Evidence Map の意味・限界・次アクションを迷わず伝える

## デモモードの起動方法

1. `streamlit run app.py` で起動し、メールアドレスでログイン
2. サイドバーの **「デモモードで読み込む：US-12565719-B2 Evidence Map」** をクリック
   - または **はじめる** タブ上部の同じボタン
3. 画面上部にデモバナーが表示され、7タブが利用可能になります

## 3分デモ手順

1. **はじめる** — ツールの目的・Deep Dive 対象・「3分デモの見方」
2. **全文確認** — BigQuery fulltext 欠落と Manual Claims Route（案内メッセージ）
3. **技術の裏取り: Evidence Map Summary** — 6枚のメトリクスカード
4. **技術の裏取り: Selected Evidence Papers** — 論文候補（supporting evidence candidate）
5. **技術の裏取り: Claim × Paper Links** — 請求項要素と論文の候補対応
6. **技術の裏取り: Evidence Gaps / Next Actions** — ギャップと次の実務ステップ
7. **レポート** — Executive Summary + `evidence_map_synthesis.md`

口頭台本は `docs/demo_script_phase21.md` を参照してください。

## Evidence Map 中心 UI の見方

特許を大量に並べるのではなく、**読むべき1件（Deep Dive Patent）** と **Evidence Gap** を中心に表示します。

### Evidence Map Summary（メトリクスカード）

| 項目 | 意味 |
|------|------|
| Deep Dive Patent | 今回深掘りしている公報番号（US-12565719-B2） |
| Route | Manual Claims Route（BigQuery fulltext で claims/description が取れなかったため） |
| Selected Evidence Papers | OpenAlex 由来の論文候補件数 |
| Claim × Paper Links | 請求項要素と論文候補の対応件数 |
| Evidence Level | claims_only / weak-to-medium（証明ではない候補レベル） |
| Status | Evidence Map ready / partial / missing / error |

Summary 直下の **読み方ガイド** で、claims_only の限界と supporting evidence candidate の位置づけを説明します。

### Selected Evidence Papers

- 実 OpenAlex 由来の論文候補
- **論文は特許主張の証明ではない** — supporting evidence candidate
- 長い title は省略表示、欠損列は `not available`
- 空の場合は warning を表示し画面は落とさない

### Claim × Paper Candidate Links

- 請求項要素（`claim_element_text` 優先）と論文タイトルの対応
- claims_only 由来の **weak / low / medium** 候補対応
- `link_type` が fallback の場合は「弱い対応」と表示
- 最終判断には専門家レビューが必要

### Evidence Gaps

現時点で確認が必要なギャップ（固定リスト + synthesis からの追加分）:

- BigQuery fulltext で claims/description が取得できなかった
- Manual Claims Route に切り替えた
- description / 実施例 / 測定条件が未確認
- claims_only 由来の confidence 上限
- CN/EP/JP Strategic Watch は manual 確認が必要
- 専門家レビューが必要

### Next Actions

研究者・中小企業が次に取るべき実務ステップ:

- description の manual 追加
- 実施例・測定条件の確認
- selected papers / Claim × Paper links のレビュー
- Strategic Watch 候補の manual 確認
- 追加1〜2件での再現性確認
- Weekly Digest Preview への反映

### レポートタブ — Executive Summary

`evidence_map_synthesis.md` の前に、Manual Route・claims_only・supporting evidence candidate・FTO/侵害/有効性非判断を短く要約します。

## 企業・市場シグナル

- 手動入力または将来拡張の対象
- **架空情報を本物のように表示しない**
- デモ用仮想シグナルは必ず **"Synthetic demo signal"** と明記
- 将来 Strategic Watch Brief（Patent / Paper / Company signal 等）として拡張予定
- **この Phase では架空企業シグナルは追加しない**

## 注意事項（全体）

- 論文は **supporting evidence candidate**（証明ではない）
- **claims_only** 由来 — confidence は最大 medium、基本 low/weak
- **FTO、侵害、有効性判断はしない**
- **専門家レビューが必要**
- **ユーザー向け UI に金額は表示しない**
- **画面を落とさない** — 成果物欠落・空 CSV・列名不一致・NaN でも継続表示

## missing artifact 時の挙動

- loader は `missing_artifacts` / `errors` に記録
- status: `ready` / `partial` / `missing` / `error`
- 利用可能な成果物だけ表示を継続

## 関連モジュール

- `src/tech_cartography/ui/evidence_map_demo.py` — loader / render / 表示整形
- `src/tech_cartography/ui/streamlit_session.py` — `activate_evidence_map_demo_state()`
- `docs/demo_script_phase21.md` — デモ台本・Q&A
- `docs/phase21_ui_state_patch_checklist.md` — session_state 回帰チェック
