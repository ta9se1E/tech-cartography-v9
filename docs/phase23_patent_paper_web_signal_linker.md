# Phase 23.4 — Patent × Paper × Web Signal Linker

## 目的

Phase 21〜23.3 で整備した Evidence Map 成果物と Web Signal Review Pack をつなぎ、**Patent × Paper × Web Signal Link Candidate** を生成します。

この Phase では Web Signal を特許・論文に**断定的に結びつけません**。技術テーマ・文脈・キーワードの重なりに基づく **link candidate** として扱います。

## Phase 23.4.1 — Link Quality Calibration

Phase 23.4.1 では、全候補が `score=100` になる過剰スコアリングを防ぎ、リンクの強弱をより誠実に表現します。

### なぜ全件 score=100 を避けるのか

- `source_quality=high`（NEDO / JST / METI 等）だけでは特許とのリンク証明にならない
- 広いキーワード（PAN 等）1語だけで高スコアにしない
- UI 表示や Strategic Watch Brief に進めるには、候補間の差別化が必要
- **Link candidates are not final conclusions**

### Term Strength 分類

| 強度 | 例 |
|------|-----|
| **strong** | carbonization, stabilization, sizing, 炭化, 前駆体 |
| **moderate** | carbon fiber, CFRP, composite, 炭素繊維, 航空機 |
| **broad** | PAN, fiber, project, 繊維, 研究開発 |

ルール:
- broad term のみでは `weak_keyword_overlap` に分類
- "pan" のみの一致は high priority にしない
- strong term があればスコア加点

### Calibrated Scoring

base: 20 + source quality / signal type / term matching / context 加点 − penalties

**confidence**（high は付けない）:
- score >= 80 → medium
- 50 <= score < 80 → low
- score < 50 → weak

### Score Cap

| 条件 | 上限 |
|------|------|
| broad term only | 45 |
| claim_element missing + paper only | 75 |
| claim_element missing + broad only | 40 |
| source_url missing | 40 |
| signal_type=human | 50 |
| ir_disclosure（文書未検証） | 70 |
| evidence_sentence missing | 70 |

### High / Top / Weak Priority の違い

| 区分 | 条件 |
|------|------|
| **top priority** | score >= 80 かつ strong/moderate term あり |
| **high priority** | score >= 70, URL/evidence あり, broad only 除外, confidence medium/low |
| **weak** | confidence=weak または weak_keyword_overlap または score < 50 |

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

## link_score の考え方（Phase 23.4.1 calibrated）

0〜100 の整数。calibrated scoring では term strength・context・penalties・caps を組み合わせます。

**confidence**: score>=80 → medium, 50-79 → low, <50 → weak（**high は付けない**）

旧スコア（`--no-calibrated-scoring`）も CLI で利用可能です。

## なぜ断定しないのか

- Web signals are signal candidates
- Papers are supporting evidence candidates
- キーワード一致は戦略判断の根拠にならない
- FTO / 侵害 / 有効性判断は対象外

## NEDO / JST / METI など公的シグナルの扱い

- `source_quality=high` でスコア加点（ただし単独では高スコアにならない）
- strong/moderate 技術語が一致すれば `project_context_match` として分類
- それでも link candidate のみ。プロジェクトページの本文確認は必須
- **source_quality=high だけではリンク証明にならない**

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
  top_priority_web_signal_links.csv
  high_priority_web_signal_links.csv
  weak_web_signal_links.csv
  patent_paper_web_signal_summary.md
  next_verification_actions.md
```

追加列（CSV）: `matched_strong_terms`, `matched_moderate_terms`, `matched_broad_terms`, `matched_term_strengths`, `link_explanation`, `score_reason`, `score_cap_reason`, `needs_manual_review`, `why_not_conclusive`

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
