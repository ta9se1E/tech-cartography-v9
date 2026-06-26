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
