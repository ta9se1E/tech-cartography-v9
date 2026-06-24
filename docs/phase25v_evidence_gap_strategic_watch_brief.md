# Phase 25V — Evidence Gap and Strategic Watch Brief

## Tech Cartography の差別化軸

| 観点 | Tech Cartography | Deep Research 型 |
|------|------------------|------------------|
| 目的 | 週次の「何が変わったか / 何が未確認か」を構造化 | 広く調べて長文レポート |
| 出力 | Evidence Gap + Next Verification Actions | 総合レポート |
| 根拠 | artifact path + safety label 付き | 本文中心 |
| 判断 | 法的判断はしない（候補のみ） | 場合により断定しがち |

## Deep Research との差分

- 外部 API を自動実行しない
- Deep Research API はこの Phase では呼ばない
- 長文ではなく **週30分** で読める Strategic Watch Brief
- 「確定事実ではない」境界を常に表示

## Evidence Gap とは

構造化された「未確認事項」:

- 何が分かっているか (`what_is_known`)
- 何が分からないか (`what_is_unknown`)
- 欠けている証拠 (`missing_evidence`)
- 次に人間が確認すべきこと (`next_verification_action`)

## Next Verification Actions

Evidence Gap から導出される優先アクション（owner / urgency 付き）。

## Strategic Watch Brief とは

研究者・技術者向けの週次ブリーフ:

1. 今週見るべき結論候補
2. 今週の変化候補
3. Evidence Gap
4. Next Verification Actions（優先3件）
5. What Not To Conclude

## 週30分で読む設計

- 優先確認事項は **3件以内**
- 読む順番を明示
- 一次情報（URL / 特許原典）への誘導

## Web Signal は候補情報

- `candidate_information_only=true`
- `verified_by_human` は自動付与しない
- FTO / 侵害 / 有効性判断はしない

## artifact 確認方法

| 種別 | パス |
|------|------|
| Evidence Gap | `outputs/live_evidence_gaps/live_evidence_gap_*.json` |
| Strategic Watch Brief | `outputs/live_strategic_watch_brief/live_strategic_watch_brief_*.json` |

## Run History

| action_type | 意味 |
|-------------|------|
| `live_evidence_gap_build` | Evidence Gap 生成 |
| `live_strategic_watch_brief_build` | Strategic Watch Brief 生成 |

## デモでの見せ方

1. Live Operation Console で gap / brief 状態を確認
2. **Evidence Gap** を生成 → gap 一覧と Next Actions
3. **Strategic Watch Brief** を生成 → 優先3件を確認
4. Digest Preview に参照セクションが付くことを確認（自動再生成なし）
5. Run History で action_type を確認

## 禁止事項

- 外部 API / Deep Research API の自動実行
- メール送信・Scheduler 起動
- Web Signal の確定事実化
- FTO / 侵害 / 有効性判断
- `verified_by_human` の自動付与
- secret の保存・表示
