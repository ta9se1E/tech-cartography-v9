# Phase 23.0 — Web Signal Foundation

## 目的

本番実行に向けて、Tavily API や Web ニュース、国家プロジェクト、公的研究費、企業活動、求人情報などの**外部 Web 情報**を安全に扱うための基盤（Web Signal Foundation）を整備します。

Phase 21 では Evidence Map デモ UI、Phase 22 では Reproducibility Smoke Run が完成しました。  
Phase 23.0 では、特許・論文に加えて **ヒト・カネ・企業・国家プロジェクト・ローカルニュース** のシグナルを扱えるようにするための**データ構造と品質ルール**を先に定義します。

## なぜ Web Signal Foundation を先に作るのか

- 外部 Web 情報は誤解を生みやすく、断定してはいけない
- ヒト・カネ情報は検証ステータスが必須
- Synthetic demo signal と実データの境界をコードで強制したい
- Tavily 等の API 実行は、スキーマとポリシーが固まってから接続する

## なぜ Tavily API をすぐ叩かないか

- API キーのハードコードや無秩序な実行を防ぐ
- 取得前に signal candidate / verification / caveat の枠組みを固定する
- Phase 23.1 以降で Adapter を追加する

## WebSignal schema

モジュール: `src/tech_cartography/web_signals/schema.py`

主要フィールド:

| フィールド | 説明 |
|-----------|------|
| signal_id | 一意 ID |
| signal_type | シグナル種別 |
| source_title / source_url / source_domain | 出典 |
| collected_at / query | 収集メタデータ |
| raw_snippet / extracted_text | 本文断片 |
| related_* | 関連エンティティ |
| confidence | high / medium / low / weak / unknown |
| verification_status | 検証状態 |
| is_synthetic_demo | デモ用仮想シグナルフラグ |
| caveat / next_verification_action | 注意と次アクション |

## signal_type 一覧

`patent`, `paper`, `human`, `money`, `company`, `local_news`, `national_project`, `policy`, `market`, `other`, `ir_disclosure`, `disclosure`, `grant`, `funding`, `equipment_investment`

## source_quality 一覧

`classify_source_quality(source_url)` の返却:

| source_quality | 例 |
|----------------|-----|
| high | jst.go.jp, nedo.go.jp, meti.go.jp, grants.jst.go.jp, kaken.nii.ac.jp |
| medium_high | 大学公式 (.ac.jp / .edu)、企業公式ドメイン |
| medium | ローカル紙、業界メディア |
| low | 求人サイト、SNS、匿名ブログ |
| unknown | 未分類ドメイン |

## Synthetic demo signal 方針

- `is_synthetic_demo=True` の場合:
  - `verification_status=synthetic_demo`
  - `confidence` は `low` または `weak`
  - `caveat` に **"Synthetic demo signal"** を必須
  - `source_title` に `[Synthetic demo signal]` プレフィックス
- 実在企業・研究者の架空シグナルは作らない
- デモサンプルは `example.invalid` 等の明示的プレースホルダーのみ

## Human signal の注意

- `verification_status != verified_source` では **high confidence 禁止**
- 人名・求人は signal candidate として weak〜medium から開始
- 必ず `next_verification_action` で人手確認を促す

## Money / national_project signal の注意

- 公的研究費・国家プロジェクトは **money signal** として扱う
- `source_url` がない場合は high confidence 禁止
- JST / NEDO / METI / GRANTS / KAKEN は high quality 候補だが、リンク確認は必須

## Local news signal の注意

- `local_news` タイプとして扱う
- 地域メディアは medium 品質候補
- 企業・技術との対応は人手確認

## 保存形式

```
outputs/web_signals/{batch_id}/
  web_signals.json
  web_signals.csv
  web_signal_summary.md
```

関数: `save_web_signal_batch`, `load_web_signal_batch`

## サンプル batch 作成

```bash
python scripts/create_web_signal_sample_batch.py \
  --topic "PAN carbon fiber mid-temperature carbonization" \
  --output-dir outputs/web_signals/sample_pan_carbon_fiber \
  --include-synthetic-examples
```

空 batch:

```bash
python scripts/create_web_signal_sample_batch.py \
  --topic "PAN carbon fiber" \
  --output-dir outputs/web_signals/empty_batch \
  --empty
```

## 今後の Phase

| Phase | 内容 |
|-------|------|
| 23.1 | Tavily Search/Extract Adapter（**完了** — `docs/phase23_tavily_web_signal_adapter.md`） |
| 23.2 | Money Signal Retriever |
| 23.3 | Local News Signal Retriever |
| 23.4 | Patent × Paper × Web Signal Linker |
| 23.5 | Strategic Watch Brief UI |

## Phase 23.1 への接続

Phase 23.1 では以下を追加しました。

- `ir_disclosure`, `disclosure`, `grant`, `funding`, `equipment_investment` などの `signal_type`
- `source_kind`, `disclosure_type`, `source_quality`, `source_category` などの任意フィールド
- Tavily Search / Extract Adapter（`--execute-tavily` 時のみ API 実行）
- PAN 炭素繊維向け query template と CLI `scripts/run_tavily_web_signal_search.py`

### IR / disclosure signal の追加

- 企業 IR・決算説明・統合報告書・有価証券報告書・適時開示を `ir_disclosure` として扱う
- EDINET / JPX ドメインは `disclosure_platform` 候補（本文確認前は `verified_source` にしない）

### 今後の専用 API 候補

| API | 目的 |
|-----|------|
| EDINET API | 提出書類 ID・書類種別・提出日の厳密取得 |
| TDnet / JPX disclosure | 適時開示の構造化取得 |
| Company official IR pages | 企業公式 IR ライブラリの直接参照 |

Phase 23.1 では Tavily 経由の Web 候補のみ。専用 API は Phase 23.2 以降。

## 禁止事項（Phase 23.0）

- Tavily API 実行
- Web スクレイピング / 自動クローリング
- 実在企業・研究者の架空シグナル
- API キーのハードコード
- FTO / 侵害 / 有効性判断
- ユーザー向け金額表示

## 関連モジュール

- `src/tech_cartography/web_signals/` — schema / quality / store / policy
- `scripts/create_web_signal_sample_batch.py` — 手動サンプル batch
