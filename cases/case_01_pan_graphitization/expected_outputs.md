# Case 01 Expected Outputs — PAN系炭素繊維

## Sources一覧

- 特許（US4370169, US5176959, EP0274055 等）と論文・Web候補を一覧表で表示
- 列: type, title, organization, year, url, publication_number, source_status, evidence_role
- 各行に artifact path（例: `outputs/cases/case_01_pan_graphitization/sources_index.json`）

## 読むべき特許 Top 5

- 請求項・実施例を読む優先順位付きリスト（最大5件）
- 各件: publication_number, title, read_priority_reason, claim_focus, artifact path
- process-property（耐炎化→炭化→黒鉛化）の主張が追えること

## Claim Map

- claim 単位または patent 単位の主張マップ
- 軸: 前駆体組成、耐炎化、炭化、黒鉛化、強度・弾性率
- 各 claim に source publication_number と artifact path

## Evidence Map

- Claim ↔ Evidence（特許実施例、論文、Web候補）の対応表
- Web Signal 行は `candidate_information_only` ラベル必須

## Evidence Gap

- 裏取り不足の主張リスト（例: 黒鉛化温度と弾性率の定量対応が論文で未確認）
- gap_id, related_claim, missing_evidence_type, severity

## Next Verification Actions

- **3件**固定: owner, action, primary_source_to_check, url, due_hint
- 例: 実施例の温度プロファイルを原典公報で確認

## 定点観測の次回検索範囲変更案

- Watch Profile 更新案（拡張/縮小/重点化/除外キーワード）
- Scheduler 次回実行とメール Digest に載せる差分の説明

## Export

- `sources_index.json`, `top_patents.json`, `claim_map.json`, `evidence_map.json`, `evidence_gap.json`, `next_actions.json`, `watch_profile_delta.json`
- 保存先: `outputs/cases/case_01_pan_graphitization/`
