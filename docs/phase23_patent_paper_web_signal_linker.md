# Phase 23.4 — Patent × Paper × Web Signal Linker

## 目的

Phase 21〜23.3 で整備した Evidence Map 成果物と Web Signal Review Pack をつなぎ、**Patent × Paper × Web Signal Link Candidate** を生成します。

この Phase では Web Signal を特許・論文に**断定的に結びつけません**。技術テーマ・文脈・キーワードの重なりに基づく **link candidate** として扱います。

## Link Candidate の考え方

| 入力 | 役割 |
|------|------|
| Claim Element | 特許請求項から抽出した技術要素 |
| Selected Evidence Papers | supporting evidence candidate |
| Claim × Paper Links | 既存の候補対応 |
| Web Signal Review Pack | NEDO / JST / METI 等の外部シグナル候補 |

出力はすべて `needs_human_review` / confidence 最大 `medium` です。

## link_type 一覧

| link_type | 意味 |
|-----------|------|
| `technology_theme_match` | Claim / Paper / Web Signal の技術語一致 |
| `project_context_match` | 国家プロジェクト・公的研究費シグナルと技術テーマ一致 |
| `paper_context_match` | 論文 title / keyword と Web Signal evidence 一致 |
| `company_context_match` | 企業 / IR / local news と技術語一致 |
| `weak_keyword_overlap` | キーワード一致はあるが文脈が弱い |
| `manual_review_required` | 人手確認なしでは判断不可 |

## link_score の考え方

0〜100 の整数。例:

- **加点**: source_quality=high (+20), national_project (+20), claim 一致 (+20), paper 一致 (+15), evidence_sentence (+10), 政府ドメイン (+10), matched_terms>=3 (+10)
- **減点**: low/unknown quality (-20), evidence なし (-10), other (-10), human (-20), source_url なし (-30)

**confidence**: score>=80 → medium, 50-79 → low, <50 → weak（**high は付けない**）

## なぜ断定しないのか

- Web signals are signal candidates
- Papers are supporting evidence candidates
- キーワード一致は戦略判断の根拠にならない
- FTO / 侵害 / 有効性判断は対象外

## NEDO / JST / METI など公的シグナルの扱い

- `source_quality=high` でスコア加点
- `project_context_match` として分類
- それでも link candidate のみ。プロジェクトページの本文確認は必須

## IR / disclosure の扱い

- `company_context_match` として分類可能
- caveat に document-level verification required
- verified_source には自動昇格しない

## 実行コマンド

```bash
python scripts/build_patent_paper_web_signal_links.py \
  --publication-number US-12565719-B2 \
  --web-signal-review-dir outputs/web_signals/tavily_pan_carbon_fiber/review_pack \
  --output-dir outputs/web_signal_links/US-12565719-B2
```

Dry run:

```bash
python scripts/build_patent_paper_web_signal_links.py \
  --publication-number US-12565719-B2 \
  --dry-run
```

## 出力ファイルの見方

```
outputs/web_signal_links/US-12565719-B2/
  web_signal_link_candidates.json
  web_signal_link_candidates.csv
  high_priority_web_signal_links.csv
  patent_paper_web_signal_summary.md
  next_verification_actions.md
```

## Next Verification Actions

- 公的プロジェクトページ・source URL の本文確認
- Claim Element と Web Signal の技術語が同じ意味か技術者確認
- selected evidence papers との関係を専門家確認
- IR / disclosure は原典 PDF / 決算説明資料を確認
- 断定的な競合戦略判断には使わない

## 注意事項

- These are link candidates, not final conclusions.
- Web signals are signal candidates, not final conclusions.
- Papers are supporting evidence candidates, not proof of patent claims.
- IR / disclosure signals require document-level verification.
- Money / national_project signals require source verification.
- This is not FTO, infringement, or validity analysis.
- Synthetic demo signal must be clearly labeled.
- 金額を断定表示しない

## 関連モジュール

- `src/tech_cartography/web_signals/linker.py`
- `scripts/build_patent_paper_web_signal_links.py`
