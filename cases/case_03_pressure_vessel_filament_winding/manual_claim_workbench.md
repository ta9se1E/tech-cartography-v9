# Manual Claim Workbench — Case 3 (CFRP圧力容器・フィラメントワインディング)

## 重要

- **このファイルは claim 本文を架空生成する場所ではありません**
- claim 本文は **ユーザーが一次情報から取得したもののみ** を投入してください

## 対象候補 publication_number

| publication_number | patent_title（参考） | 推奨 claim_no |
|--------------------|----------------------|---------------|
| US4878636 | Filament winding pressure vessel | 1 |
| US7758784 | Composite pressure vessel | 1 |
| US6887393 | Hydrogen storage tank | 1 |
| US4214937 | Filament wound structure | 1 |

## 手順

1. 一次情報から実 claim 本文をコピー
2. Claim Map タブで手動投入 → `claims_input.csv` へ保存
3. 再生成スクリプトまたは UI で downstream artifact を更新

```bash
conda run -n 2026hack python scripts/run_v8_manual_claim_refresh.py \
  --case-id case_03_pressure_vessel_filament_winding \
  --publication-number US4878636 \
  --claim-no 1
```

## 注意

- FTO / 侵害 / 有効性 / 権利範囲解釈ではありません

## claim_text 貼り付け欄（placeholder）

```
（ここにユーザー取得の claim 本文を貼り付け）
```
