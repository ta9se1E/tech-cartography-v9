# Phase 25J — Watch Profile Driven Next Cycle Search

## Phase 25I との差分

| Phase | 内容 |
|-------|------|
| 25I | Web Signal → Watch Expansion Proposal → 人間承認 → Watch Profile Draft |
| **25J** | **Watch Profile Draft → Next Cycle Search Plan → 人間選択 → 手動 Tavily → Next Cycle Web Signal Pack** |

## Watch Profile Draft から次回検索クエリを作る意味

承認済み monitoring scope（keywords / companies / technology terms 等）を、次の Tavily 検索サイクルへつなぐためです。Draft は **確定 fact ではなく**、query 候補生成の入力に過ぎません。

## Human selection 設計

- 各 query candidate: `review_status=pending_human_selection`
- `safety_label`: `Next cycle search candidate`
- admin が checkbox で選択した query **のみ** Tavily 実行
- 最大 **5 個** の query 候補 / 最大 **3 個** の実行 query

## Tavily 実行上限

| 制限 | 値 |
|------|-----|
| query 候補数 | 最大 5 |
| 実行 query 数 | 最大 3 |
| max_results_per_query | 1〜3 |
| search_depth | basic（固定） |

## DISABLE_EXTERNAL_API

| 値 | 動作 |
|----|------|
| `true` | Tavily を **絶対に呼ばない**（plan 作成のみ可） |
| `false` + `TAVILY_API_KEY` 設定 | admin 選択 query のみ手動実行 |

## 保存ファイル

### Next Cycle Search Plan

`LIVE_OUTPUTS_ROOT/live_next_cycle_search/`

- `next_cycle_search_plan_<timestamp>.json|csv|md`

### Next Cycle Web Signal Pack

`LIVE_OUTPUTS_ROOT/live_next_cycle_web_signals/`

- `next_cycle_web_signal_pack_<timestamp>.json|csv|md`

各 signal: `review_status=needs_human_review`, `safety_label=Next cycle Web Signal candidate`

## Digest Preview 連携

pack に `source_type` を付与:

- `live_web_signal_pack` — Phase 25E 由来
- `next_cycle_web_signal_pack` — Phase 25J 由来

Digest Preview は **最新 mtime の pack** を自動選択。メール送信は Phase 25J では行いません。

## scheduler / 自動週次

**まだ OFF** です。手動 admin 実行のみ。

## 次 Phase

週次運用ループの **手動実行パネル** へ進む方針。

## 禁止事項

- scheduler ON / 自動週次 / 一斉メール
- 全 query 自動実行
- 本番 Watch Profile 自動反映
- API キー・SMTP_PASSWORD 表示・保存
- FTO / 侵害 / 有効性判断
