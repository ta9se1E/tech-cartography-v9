# Phase 25I — Human-approved Watch Expansion Proposal

## Phase 25E〜25H との差分

| Phase | 内容 |
|-------|------|
| 25E | Web Signal Pack 作成・保存 |
| 25F | Digest Mail Preview（送信なし） |
| 25G | Self-only Email Send Test |
| 25H | `LIVE_OUTPUTS_ROOT` / Cloud Storage mount による永続化 |
| **25I** | **Web Signal から監視範囲拡張候補を提案し、人間承認後のみ Watch Profile Draft へ保存** |

## なぜ Web Signal から拡張候補を作るか

Live Tavily 検索で得た Web Signal candidate は、次の監視サイクルで追うべきキーワード・企業・技術観点の手がかりになります。ただし **確定事実ではない** ため、自動で Watch Profile を広げず、人間が承認した項目だけ draft に反映します。

## ルールベース提案（Gemini/OpenAI 非必須）

Phase 25I では title / snippet / url からルールベースで以下を抽出します。

- 企業名らしき語（Inc./Corp./Ltd. 等、既知企業リスト）
- NEDO / JST / METI / DOE / EU 等の公的機関
- recycling, precursor, PAN, CFRP, oxidation 等の技術語
- aerospace, automotive, wind energy 等の application 語
- grant / project / demonstration 等の公的プロジェクト語
- stock price / earnings call 等の除外候補（exclusion_term）

**これらは提案であり、市場事実・法的判断ではありません。**

## Human approval 設計

- 各 proposal の `review_status` は `pending_human_review`
- `safety_label`: `Watch expansion proposal`
- UI で checkbox → **承認** または **却下**
- 承認された項目のみ Watch Profile Draft の `approved_*` リストへ
- 却下項目は `rejected_items` に記録
- **本番 Watch Profile（`watch_profile_store`）は直接上書きしない**

## 保存仕様

### Watch Expansion Proposals

`LIVE_OUTPUTS_ROOT/live_watch_expansion/`（未設定時は `outputs/live_watch_expansion/`）

| ファイル | 内容 |
|---------|------|
| `live_watch_expansion_proposals_<timestamp>.json` | theme_name, source paths, proposals, safety_notice |
| `live_watch_expansion_proposals_<timestamp>.csv` | proposal 一覧 |
| `live_watch_expansion_proposals_<timestamp>.md` | 人間可読サマリー |

### Watch Profile Draft

`LIVE_OUTPUTS_ROOT/live_watch_profiles/`

| ファイル | 内容 |
|---------|------|
| `watch_profile_draft_<timestamp>.json` | approved_* リスト, rejected_items, approved_by/at |
| `watch_profile_draft_<timestamp>.md` | 同上（Markdown） |

## Cloud Run live

Phase 25H と同様、Cloud Storage mount 先の `LIVE_OUTPUTS_ROOT` 配下に proposals / draft が永続化されます。

## UI

- **入力・実行タブ（admin）:** Watch Expansion Proposals（承認前）
- **レポート / 設定タブ:** Approved Watch Profile Draft（人間承認済み）

## 次 Phase

Phase 25I 完了後、**週次運用ループ**（scheduler 連携は別 Phase）へ進む方針です。

## 禁止事項（25I）

- 自動 Watch Profile 本番反映
- scheduler ON
- 一斉メール
- Gemini/OpenAI 必須化
- FTO / 侵害 / 有効性判断
- API キー・SMTP_PASSWORD の表示・保存
