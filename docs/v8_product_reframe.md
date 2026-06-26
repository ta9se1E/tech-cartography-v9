# v8 Product Reframe — Claim / Evidence / Gap / Next Action / 定点観測ループ

## v8 サービス定義

Tech Cartography は、日本の研究者・中小製造業の技術者向けに、特許の請求項・実施例・論文・Web情報を対応付け、**読むべき特許**、**技術的に確認すべき主張**、**裏取り不足の Evidence Gap**、**次に確認すべき一次情報**を提示し、その結果を **Watch Profile・Scheduler・メール送信** を使った **定点観測ループ** に反映する R&D Intelligence Agent である。

## v7 でできていること

| 領域 | 状態 |
|------|------|
| Cloud Run + IAP + Cloud Storage 永続化 | 運用基盤として整備済み |
| Watch Profile 管理 | active / draft / archive |
| Web Signal 手動収集 | 候補情報として Digest 統合 |
| Digest Preview | IAP admin ガード、Web Signal 統合 |
| Evidence Gap / Strategic Watch Brief | artifact 読み取りベース |
| Weekly Decision Cockpit | 週次判断の1画面集約 |
| Run History | 操作記録・監査向け |
| メール送信 / Scheduler | 実装あり（デフォルト OFF、機能は保持） |
| Scope Expansion / Feedback | Watch 拡張提案 |

## v7 でズレていたこと

- ユーザー画面の主役が **運用コンソール・管理者設定・IAP/SMTP 詳細** に寄りすぎた
- **Claim Map / Evidence Map / 読むべき特許** が UI の中心ではなかった
- 7タブ以上の構成で、初見ユーザーが「何から見ればよいか」迷いやすかった
- Deep Research 型の長文レポート志向に見えやすく、**定点観測ループ** の価値が伝わりにくかった

## v8 で前面に出すもの

1. **Sources一覧** — 特許・論文・Web の出典と artifact path
2. **読むべき特許 Top N** — 請求項・実施例を読む優先順位
3. **Claim Map** — 請求項・技術主張の構造化
4. **Evidence Map** — Claim と Evidence（論文・実施例・Web 候補）の対応
5. **Evidence Gap** — 何が未確認か
6. **Next Verification Actions** — 人間が次に見る一次情報
7. **定点観測ループ** — Watch Profile 更新 → Scheduler → メール Digest
8. **Export** — 案件ごとの検証成果物出力

## v8 で裏側に回すもの

- Cloud Run 状態 / IAP 詳細
- SMTP パスワード・送信設定の詳細
- Scheduler の cron / Cloud Scheduler 詳細
- Operation Status の内部フラグ
- Run History の生 JSON（管理者タブでのみ）

## 必須で残す機能

| 機能 | 理由 |
|------|------|
| **メール送信** | 定点観測ループの成果を週次で届ける必須経路 |
| **Scheduler** | 定点観測の自動トリガー（デフォルト OFF、機能は保持） |
| **Watch Profile** | 検索範囲・キーワードの定点管理 |
| **Scope Expansion / Feedback** | 検索範囲の拡張・縮小・重点化 |
| **Run History** | 操作の追跡・デモ説明 |
| **Cloud Storage artifact** | 永続化・再現性 |
| **Digest Preview** | メール下書き・週次サマリー |

## やらないこと

- FTO 判断 / 侵害判断 / 有効性判断 / 法的結論
- 架空情報を本物のように表示すること
- Deep Research API の本番導線
- Cloud SQL 追加
- v7 の Cloud Run / IAP / 既存 artifact パイプラインの削除

## v8 MVP 成功条件

1. **3案件**（PAN 黒鉛化 / サイジング界面 / CFRP 圧力容器）で以下が artifact 付きで出る:
   - Sources一覧、読むべき特許 Top 5、Claim Map、Evidence Map、Evidence Gap、Next Actions 3件、定点観測変更案、Export
2. 各出力に **source url / artifact path** が残る
3. Web Signal は **候補情報** としてラベル付き
4. **メール Digest + Scheduler** につながる定点観測ループが画面で説明できる
5. ローカルで納得できる品質になるまで **Cloud Build を必須にしない**
