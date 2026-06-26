# Manual Claim Workbench — Case 1 (PAN 前駆体・炭化・黒鉛化)

## 重要

- **このファイルは claim 本文を架空生成する場所ではありません**
- claim 本文は **ユーザーが一次情報から取得したもののみ** を `claims_input.csv` または Claim Map UI に投入してください
- システムは claim 本文を生成しません

## 対象候補 publication_number

| publication_number | patent_title（参考） | 推奨 claim_no |
|--------------------|----------------------|---------------|
| US5176959 | Process for producing carbon fibers from PAN | 1 |
| US4370169 | Method for producing carbon fibers | 1 |
| US3969557 | Process for producing high strength carbon fibers | 1 |
| US4532173 | Manufacture of carbon fibers | 1 |

## 手順

1. Google Patents / BigQuery / PDF / 手元資料から **実 claim 本文** をコピー
2. Streamlit **Claim Map** タブ → 「claim本文を手動投入する」
3. `case_01_pan_graphitization` / publication_number / claim_no / claim_text を入力
4. `claim_source_type` を選択（例: `google_patents_user_copy`）
5. 「claims_input.csvへ保存」をクリック
6. 「Claim Mapを再生成」→「Evidence Mapまで再生成」案内に従う

または CLI:

```bash
conda run -n 2026hack python scripts/run_v8_manual_claim_refresh.py \
  --case-id case_01_pan_graphitization \
  --publication-number US5176959 \
  --claim-no 1
```

## 注意

- FTO 判断ではありません
- 侵害判断ではありません
- 有効性判断ではありません
- 権利範囲解釈ではありません
- Claim Map は技術整理（heuristic / draft）です

## claim_text 貼り付け欄（placeholder）

```
（ここにユーザー取得の claim 本文を貼り付け — システムは自動入力しません）
```
