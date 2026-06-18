# Phase 23.3 — Web Signal Review UI

## 目的

Phase 23.2 で整理した **Web Signal Review Pack** を、Streamlit UI の **「企業・市場シグナル」** タブで人間がレビューしやすく表示します。

この Phase では **新しい Tavily 実行は行いません**。  
`outputs/web_signals/*/review_pack/` の既存成果物を読み込んで表示するだけです。

## Web Signal Review UI の表示場所

- アプリ: `streamlit run app.py`
- タブ: **企業・市場シグナル**（`translate_tab_name("market")`）
- モジュール: `src/tech_cartography/ui/web_signal_review_ui.py`
- 呼び出し: `src/tech_cartography/ui/v7_easy_app.py` の `_tab_market()`

## Summary Cards の意味

| カード | 意味 |
|--------|------|
| Total Review Signals | `web_signal_review_items.csv` の件数 |
| High Priority Signals | `high_priority_web_signals.csv` |
| Money / National Project Signals | 公的研究開発・国家プロジェクト候補 |
| IR / Disclosure Signals | IR / 開示候補 |
| Company / Local News Signals | 企業・地方ニュース候補 |
| Rejected / Low Quality Sources | 監査用に退避した低品質候補 |

CSV が無い場合は `0` 表示し、画面は落ちません。

## High Priority Web Signals の見方

- `review_priority` 降順で表示
- `source_quality=high`（NEDO / JST / METI 等）を優先確認
- `source_url` は Markdown リンク形式
- `evidence_sentences` は 120〜200 文字程度で省略
- **特許・論文との関係はこの段階では断定しない**

## Money / National Project Candidates の見方

- NEDO / JST / METI などの国家プロジェクト・研究開発候補
- **金額を断定表示しない**（プロジェクト・研究開発シグナルとして扱う）
- `related_project` / `related_institution` / `related_technology_terms` を確認
- 元資料の URL を開いて人手検証

## IR / Disclosure Candidates の見方

- 決算説明・統合報告書・有価証券報告書・適時開示などの候補
- 空の場合は info メッセージで次 Phase（EDINET / JPX / 企業 IR）を案内
- `verified_source` には自動昇格しない

## Company / Local News Candidates の見方

- 企業プレスリリース・地方紙・自治体ニュース候補
- 空でも落ちず info 表示

## Rejected / Low Quality Sources の意味

- デフォルト閉じの expander
- URL なし・内容薄・低品質などの監査用一覧
- 削除ではなく保存

## Web signals are signal candidates の方針

タブ上部に英語・日本語の注意文を必ず表示します。

- Web シグナルは最終結論ではない
- 公的ソースでも特許・論文との関係は人手確認が必要
- FTO / 侵害 / 有効性判断ではない
- Synthetic demo signal は必ずラベル付け

## NEDO / JST / METI など高品質ソースの扱い

- `source_quality=high` を優先表示
- それでも **signal candidate** として扱う
- Evidence Map への自動接続は次 Phase

## 金額を断定しない方針

- UI では金額を主張として強調しない
- evidence 内に金額らしき記述があっても、断定ラベルは付けない
- 金額抽出・検証は別 Phase

## IR 候補が空の場合の次アクション

- 企業公式 IR、EDINET、JPX/TDnet、統合報告書、決算説明資料へ対象を広げる
- Phase 23.4 以降の Linker 実装を待つ

## 次 Phase: Patent × Paper × Web Signal Linker

- Claim Element / Selected Evidence Papers / Web Signal の技術語照合
- `technology_theme_match` / `source_overlap` / `project_context_match` など候補リンク
- 断定ではなく link candidate として扱う

## 関連モジュール

- `src/tech_cartography/ui/web_signal_review_ui.py`
- `src/tech_cartography/ui/v7_easy_app.py`
