# Phase 21 — Evidence Map デモ台本

ハッカソン審査・研究者・中小企業向けの口頭デモ用台本です。

## 1分版

1. **ログイン** — メールアドレスのみ（開発用）
2. **デモモード** — サイドバー「US-12565719-B2 Evidence Map」をクリック
3. **はじめる** — 「読むべき特許1件に深掘りする」ツールであることを説明
4. **技術の裏取り** — Evidence Map Summary で「請求項×論文候補の対応づけまでできている」と示す
5. **注意** — 論文は supporting evidence candidate。FTO・侵害・有効性判断ではない

**締め**: 「次に何を確認すべきか（Evidence Gaps / Next Actions）まで一画面で分かります。」

---

## 3分版（Phase 21.2 + 22.1）

1. **はじめる** — Tech Cartography の流れと Deep Dive 対象（US-12565719-B2）
2. **再現性確認の現在地** — 「1件 Evidence Map ready / 2件 Manual Claims Route required」カードを説明
3. **全文確認** — BigQuery fulltext で claims/description が取れず Manual Claims Route へ（案内メッセージ）
4. **技術の裏取り: Summary** — 6枚のメトリクスカード
5. **Selected Evidence Papers / Claim × Paper Links** — supporting evidence candidate
6. **Evidence Gaps / Next Actions** — 実務で次にやること
7. **企業・市場シグナル** — Web Signal Review Pack（NEDO / JST / METI 国家プロジェクト候補）
8. **レポート** — Executive Summary + **Reproducibility Smoke Run** 詳細セクション

**Patent × Paper × Web Signal Link（Phase 23.4）**:

- 「Review Pack で見た NEDO / JST シグナルを、US-12565719-B2 の Claim Element / 論文候補と **link candidate** として横断整理できます」
- 「**これは最終結論ではなく、次に確認すべき横断シグナルです** — 技術語が重なっても、同じ意味とは限りません」
- 「`project_context_match` は国家プロジェクト文脈の候補であり、FTO・侵害・有効性判断ではありません」

**Web Signal の話し方（Phase 23.3）**:

- 「特許・論文だけでなく、NEDO / JST / METI などの **国家プロジェクト・公的研究開発シグナル候補** も見られます」
- 「**これは最終結論ではなく、次に確認すべき外部シグナルです** — 特許・論文との関係はまだ人間が確認します」
- 「`source_quality=high` でも signal candidate として扱い、FTO・侵害・有効性判断ではありません」
- 「IR / disclosure 候補が空でも画面は落ちず、次 Phase で EDINET / 企業 IR を広げる予定です」

**再現性の話し方（Phase 22.1）**:

- 「US-12565719-B2 以外の追加2件（US-12435451-B2 / US-12516451-B2）も同じパイプラインで診断しました」
- 「2件は `blocked_missing_manual_claims` — **失敗ではなく**、claims 手動投入が次のステップだと分かった状態です」
- 「1件だけの偶然ではなく、候補ごとに状態管理できています」

**締め**: 「読むべき1件の深掘りと、追加候補の再現性診断の両方を見せられます。」

---

## 3分版（Phase 21.2 のみ・旧）

1. **はじめる** — Tech Cartography の流れと Deep Dive 対象（US-12565719-B2）
2. **全文確認** — BigQuery fulltext で claims/description が取れず Manual Claims Route へ（案内メッセージ）
3. **技術の裏取り: Summary** — 6枚のメトリクスカード（特許・Route・論文数・リンク数・Evidence Level・Status）
4. **読み方ガイド** — claims_only の限界を明示
5. **Selected Evidence Papers** — OpenAlex 由来の候補（証明ではない）
6. **Claim × Paper Links** — weak / low / medium の候補対応
7. **Evidence Gaps / Next Actions** — 実務で次にやること
8. **レポート** — Executive Summary + synthesis.md

**締め**: 「大量の特許リストではなく、読むべき1件とギャップに集中します。」

---

## 5分版

3分版に加えて:

- **企業・市場シグナル** — Web Signal Review Pack（NEDO/JST/METI 候補）。架空情報は使わない方針
- **設定** — Watch テーマ・週次メール設定（送信は未実装）
- **堅牢性** — 成果物が一部欠けても画面は落ちず partial 表示
- **再現性** — 追加1〜2件の特許で同じフローを試せる設計意図

---

## 審査員 Q&A

### 「1件だけではないのか？」

Carbon fiber ケースでは **Deep Dive 1件（US-12565719-B2）** をデモの中心に置いています。  
**Phase 22** では追加候補（US-12435451-B2 / US-12516451-B2）も Reproducibility Smoke Run で診断し、UI の「再現性確認の現在地」カードに表示します。  
追加2件は `blocked_missing_manual_claims` ですが、**これは失敗ではなく、次に必要な manual action（claims 投入）が明確になった状態**です。  
1件デモは価値の見せ方であり、製品は複数件の候補を状態管理できます。

### 「論文が特許を証明しているのか？」

**いいえ。** 論文は **supporting evidence candidate**（技術背景の裏取り候補）です。  
claims_only 由来のため confidence は基本 low/weak、最大 medium です。  
FTO、侵害、有効性判断はしません。最終判断には専門家レビューが必要です。

### 「架空情報は使っているのか？」

**Evidence Map デモの論文・リンクは既存 outputs（OpenAlex 実行結果）から読み込んでいます。**  
企業・市場シグナルは **Web Signal Review Pack（Tavily 取得済み review_pack）** を表示します。架空情報を本物のように表示しません。  
将来デモ用の仮想シグナルを使う場合は、必ず **"Synthetic demo signal"** と明記するルールです。

### 「中小企業にどう役立つのか？」

- 特許を全部読むのではなく、**読むべき1件と確認ギャップ**に集中できる  
- 論文候補との対応を整理し、**技術者・専門家が次に何を確認すべきか**が分かる  
- BigQuery / OpenAlex の新規実行は UI から行わず、**コストと判断リスクを抑える**  
- FTO 判断はせず、**調査のたたき台**として使える

---

## 手動確認チェックリスト（デモ前）

- [ ] `streamlit run app.py` で起動できる
- [ ] デモモードボタンでバナーと 7 タブが表示される
- [ ] はじめるタブに「3分デモの見方」がある
- [ ] 技術の裏取りタブに Summary カード・ガイド・Gaps・Next Actions がある
- [ ] レポートタブ先頭に Executive Summary がある
- [ ] 企業・市場シグナルに Web Signal Review Pack（Summary Cards / High Priority）がある
- [ ] 企業・市場シグナルに「signal candidates / FTOではない」注意文がある
