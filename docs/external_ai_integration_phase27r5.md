# External AI Integration — Phase 27R.5 (Design / OFF)

## 目的

Gemini / Deep Research / 外部AIを将来利用し、以下を高度化するための設計を定義する。

- Top5 ranking explanation
- Evidence Map Executive Summary
- Gap Executive Summary
- Weekly Digest draft

**本 Phase では本番実行・外部API常時接続は行わない。** 提出デモでは既存データに基づくローカル要約のみ表示する。

## 対象と出力の範囲

| 対象 | 出力の性質 | 禁止 |
|------|-----------|------|
| Top5 ranking explanation | 既存 ranking artifact に基づく draft 要約 | 順位の LLM 丸投げ |
| Evidence Map Executive Summary | 裏取り候補の整理サマリー | 「証明」表現 |
| Gap Executive Summary | 未確認事項・次アクションの draft | 弱点・無効・侵害表現 |
| Weekly Digest draft | 定点観測 Digest preview の下書き | 自動送信 |

## 利用候補（将来）

- **Gemini** — 長文要約・構造化サマリー
- **Deep Research 系ワークフロー** — 多段探索（人手承認後）
- **OpenAlex 追加探索** — 論文候補の拡張（既存データと突合）
- **Web 検索** — 企業・製品シグナル（ENABLE_LIVE_WEB_RESEARCH）

## Feature Flags（デフォルト OFF）

| 環境変数 | デフォルト | 説明 |
|---------|-----------|------|
| `ENABLE_EXTERNAL_AI_SUMMARY` | `false` | 外部AI要約のマスター开关 |
| `ENABLE_GEMINI_DEEP_RESEARCH` | `false` | Gemini / Deep Research 連携 |
| `ENABLE_LIVE_WEB_RESEARCH` | `false` | ライブ Web 調査 |

実装: `src/tech_cartography/runtime/v8_external_ai_config.py`  
プレースホルダ: `src/tech_cartography/services/v8_external_ai_summary.py`

## 安全設計

外部AI出力に対する必須要件:

1. **citations / source trace required** — 既存 artifact パスまたは引用元を明示
2. **no generated claims** — 請求項本文を生成しない
3. **no generated DOI / URL / 特許番号**
4. **no legal judgement** — FTO / 侵害 / 有効性を述べない
5. **output labeled as draft summary**
6. **human review required** — Watch Profile / Digest へ自動反映しない
7. **fake evidence を作らない**

## 公開デモ方針

- 外部AI実行ボタンは **無効** または **管理者設定の expander 内のみ**
- UI 表示: 「提出デモでは実行せず、既存データに基づくローカル要約のみ」
- `execute_external_ai_summary()` は RuntimeError で明示的に拒否

## 既存機能との接続（将来）

外部AI要約は以下へ接続可能な設計とする（本 Phase では送信・起動・自動反映しない）:

- Weekly Digest draft（Email Digest Plan）
- Watch Profile update proposal
- Scope Expansion / Feedback
- Email preview
- Scheduler follow-up plan

メール送信、Scheduler、Watch Profile、検索範囲拡張機能は **削除しない**。

## 実装ファイル

```
src/tech_cartography/runtime/v8_external_ai_config.py
src/tech_cartography/services/v8_external_ai_summary.py
docs/external_ai_integration_phase27r5.md
```

## 検証

```bash
grep -RE "ENABLE_EXTERNAL_AI_SUMMARY|ENABLE_GEMINI_DEEP_RESEARCH|ENABLE_LIVE_WEB_RESEARCH" src docs scripts tests
python -m pytest tests/test_v8_external_ai_summary_phase27r5.py -q
```
