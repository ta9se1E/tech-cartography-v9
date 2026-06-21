# Phase 25E — Live Tavily Web Signal Pack Integration

## 目的

Phase 25D の admin 限定 Tavily 単発検索を拡張し、検索結果を **Web Signal candidate pack** として構造化・保存・表示する。

## Phase 25D との差分

| Phase 25D | Phase 25E |
|-----------|-----------|
| Tavily 生結果を `outputs/live_search/` に保存 | Web Signal candidate に変換して `outputs/live_web_signals/` に保存 |
| smoke test テーブル表示のみ | signal_type / confidence / review_status 付き pack |
| 市場タブ連携なし | 「企業・市場シグナル」タブに最新 pack を表示 |

## Web Signal candidate の意味

- Tavily 検索ヒットを **人間レビュー用の確認候補** として整形したもの
- **確定事実・直接関係の証明・FTO / 侵害 / 有効性判断ではない**
- `review_status=needs_human_review` 固定
- `safety_label=Web Signal candidate` 固定

## signal_type 候補

| 値 | 目安 |
|----|------|
| `company_signal` | 企業 IR / プレスリリース等 |
| `public_project_signal` | 公的プロジェクト / 補助金 / .go.jp |
| `market_signal` | 市場・需要・業界 |
| `research_signal` | 研究・論文・特許 |
| `unknown` | 上記に当てはまらない |

## 保存ファイル仕様

保存先: `outputs/live_web_signals/`

| ファイル | 内容 |
|----------|------|
| `live_web_signal_pack_<timestamp>.json` | theme_name, query, fetched_at, provider, candidates, safety_notice, next_actions |
| `live_web_signal_pack_<timestamp>.csv` | candidates 一覧 |
| `live_web_signal_pack_<timestamp>.md` | 人間可読サマリー |

**API キーは含めない**

## UI

### 入力・実行タブ（admin のみ）

- `REQUIRE_LOGIN=true` + role=admin
- expander: **Live Web Signal Pack（管理者向け）**
- theme_name / query / max_results(1–3)
- **「Web Signal Packを作成」** ボタン

### 企業・市場シグナルタブ

- demo mode では **表示しない**
- analyst / live mode で最新 pack がある場合:
  - expander: **Live Web Signal Candidates（確認候補）**
  - title / url / snippet / signal_type / confidence_label / review_status

既存 US-12565719-B2 demo 表示は変更しません。

## 外部 API ガード（Phase 25D 継続）

- `DISABLE_EXTERNAL_API=true` → Tavily 不実行
- `DISABLE_EXTERNAL_API=false` + `TAVILY_API_KEY` 設定時のみ実行
- admin / ログイン必須
- max_results ≤ 3
- エラー時も UI は落とさない

## API credit 注意

- 1 pack 作成 = Tavily API 1 回
- 乱発しないこと

## まだ OFF のもの

- メール送信（`DISABLE_EMAIL_SEND=true`）
- scheduler（`DISABLE_SCHEDULER=true`）
- Gemini / OpenAI 実行
- 特許検索パイプライン全体

## 次 Phase

- メールプレビュー（Digest preview → 週次メール下書き）への接続を予定

## 関連モジュール

- `src/tech_cartography/services/live_web_signal_pack.py`
- `src/tech_cartography/ui/live_web_signal_pack_ui.py`
- `src/tech_cartography/services/live_tavily_search.py`（Tavily 呼び出し）
