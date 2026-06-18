# Phase 23.5 — Strategic Watch Brief

## 目的

Phase 21〜23.4.1 で生成した Evidence Map、Paper Evidence、Web Signal Link Candidate を統合し、研究者・中小企業ユーザーが「次に何を監視・確認すべきか」を理解するための **Strategic Watch Brief** を生成・UI表示します。

## Strategic Watch Brief とは

特許・論文・Webシグナルを横断して、**重点監視候補（Strategic Watch Candidate）** を整理した実務向けブリーフです。

- 最終結論ではない
- FTO / 侵害 / 有効性判断ではない
- high confidence は付与しない

## Patent × Paper × Web Signal Link Candidate との違い

| 段階 | 役割 |
|------|------|
| Link Candidate (23.4) | 技術語・文脈の重なりをスコアリング |
| Strategic Watch Brief (23.5) | 監視テーマ・優先度・次アクションに整理 |

Link Candidate が Watch Item に変換され、UIで一覧表示されます。

## watch_type 一覧

| watch_type | 意味 |
|------------|------|
| `patent_paper_web_signal` | 特許×論文×Webの横断候補 |
| `national_project_signal` | 国家プロジェクト |
| `money_signal` | 資金・助成 |
| `ir_disclosure_signal` | IR / 開示 |
| `company_signal` | 企業シグナル |
| `local_news_signal` | 地域ニュース |
| `evidence_gap` | Evidence Map のギャップ |
| `next_action` | 次アクション |

## watch_priority の意味

| priority | 意味 |
|----------|------|
| `high` | 注目度が高い（**事実確定ではない**） |
| `medium` | 中程度の監視価値 |
| `low` | 参考候補・保留 |

## フィールドの意味

- **why_it_matters**: なぜ監視価値があるか（短い説明）
- **evidence_basis**: 根拠（ソース・用語・link_type 等）
- **evidence_gap**: 未確認事項
- **next_verification_action**: 次に取るべき確認アクション

## UI 表示場所

「企業・市場シグナル」タブ → Web Signal Review UI の下に Strategic Watch Brief セクション

## 実行コマンド

```bash
python scripts/build_strategic_watch_brief.py \
  --publication-number US-12565719-B2 \
  --web-signal-link-dir outputs/web_signal_links/US-12565719-B2 \
  --output-dir outputs/strategic_watch_briefs/US-12565719-B2
```

Dry run:

```bash
python scripts/build_strategic_watch_brief.py \
  --publication-number US-12565719-B2 \
  --dry-run
```

## 出力ファイル

```
outputs/strategic_watch_briefs/US-12565719-B2/
  strategic_watch_brief.json
  strategic_watch_items.csv
  top_strategic_watch_items.csv
  strategic_watch_brief.md
  strategic_watch_next_actions.md
```

## 注意事項

- This is a Strategic Watch Brief, not a final conclusion.
- Web signals are signal candidates, not final conclusions.
- Papers are supporting evidence candidates, not proof of patent claims.
- This is not FTO, infringement, or validity analysis.
- IR / disclosure signals require document-level verification.
- Money / national_project signals require source verification.
- Synthetic demo signal must be clearly labeled.
- 金額を断定表示しない

## 関連モジュール

- `src/tech_cartography/strategic_watch/brief_builder.py`
- `src/tech_cartography/strategic_watch/store.py`
- `src/tech_cartography/ui/strategic_watch_ui.py`
- `scripts/build_strategic_watch_brief.py`
