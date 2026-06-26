# Manual Claim Workbench — Case 2 (サイジング・界面・複合材料)

## 重要

- **このファイルは claim 本文を架空生成する場所ではありません**
- claim 本文は **ユーザーが一次情報から取得したもののみ** を投入してください

## 対象候補 publication_number

| publication_number | patent_title（参考） | 推奨 claim_no |
|--------------------|----------------------|---------------|
| US5962187 | Sizing composition for carbon fibers | 1 |
| US5916936 | Surface treatment of carbon fibers | 1 |
| US6287695 | Interface between fiber and matrix | 1 |
| US4828969 | Composite material with carbon fiber | 1 |

## 手順

1. 一次情報から実 claim 本文をコピー
2. Claim Map タブで手動投入 → `claims_input.csv` へ保存
3. Claim Map / Evidence Map / Gap / 定点観測を再生成

```bash
conda run -n 2026hack python scripts/run_v8_manual_claim_refresh.py \
  --case-id case_02_sizing_interface \
  --publication-number US5962187 \
  --claim-no 1
```

## 注意

- FTO / 侵害 / 有効性 / 権利範囲解釈ではありません

## claim_text 貼り付け欄（placeholder）

```
（ここにユーザー取得の claim 本文を貼り付け）
```
