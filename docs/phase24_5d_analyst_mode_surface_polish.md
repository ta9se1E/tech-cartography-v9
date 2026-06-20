# Phase 24.5D — Analyst Mode Surface Polish

## 目的

Phase 24.5A〜C で整理した Demo mode と同じ思想を、本番実行（Analyst）モードにも適用する。
本番実行では入力・実行操作が必要なため、先頭に **入力・実行** タブを置き、その後の結果閲覧タブは Demo と揃える。

## Demo mode との違い

| 項目 | Demo mode | 本番実行（Analyst） |
|------|-----------|---------------------|
| 先頭タブ | はじめる | **入力・実行** |
| 成果物 | US-12565719-B2 固定デモ | ユーザー入力 theme_id / seed の outputs |
| 入力 UI | なし | テーマ・Manual Claims・E2E Chain |
| 未生成時 | デモ成果物を表示 | 「入力・実行タブで先に実行してください」 |

## 本番実行タブ構成

1. 入力・実行
2. はじめる
3. 技術の裏取り
4. 企業・市場シグナル
5. レポート
6. 設定

非表示（開発者向けまたは旧導線）: 特許候補、全文確認、別テーマ検証（独立タブ）、scheduler / raw validation summary

## 入力・実行タブ

見出し: **本番実行 / 新しいテーマで分析**

説明: 新しい技術テーマと seed 公報を入力し、Manual Claims から Evidence Map、Paper/Web、Link、Watch、Digest まで順番に生成する。

### Step 1〜7

| Step | 内容 | 状態例 |
|------|------|--------|
| 1 | テーマを入力する | 完了 / 次にやる |
| 2 | seed 公報を入力する | 完了 / 次にやる |
| 3 | Manual Claims を保存する | 完了 / 要確認 |
| 4 | Evidence Map skeleton を生成する | 完了 / 未実行 |
| 5 | Paper / Web 候補を取得する | 外部API同意が必要 |
| 6 | Link / Watch / Digest を生成する | 未実行 |
| 7 | 結果を見る | 完了 |

入力 UI は expander で分割:

1. テーマ・seed 入力（dry-run / 既存 outputs 検証含む）
2. Manual Claims
3. Evidence Map 生成
4. Paper/Web/Link/Watch/Digest（JP Seed End-to-End Chain）
5. Final Validation

## PAN 前駆体テーマ読み込み

入力・実行タブ冒頭の **PAN前駆体欠陥制御テーマを読み込む** で以下を復元:

- theme_id: `pan_precursor_surface_internal_defects`
- theme_name: PAN系炭素繊維前駆体の表面・内部欠陥制御
- core / 用途 / 材料・プロセス / 除外キーワード
- seeds: JP2022090764A, JP2023163084A, JP2018084002A

## 結果閲覧タブ

技術の裏取り / 企業・市場シグナル / レポートは Demo と同様のカード・圧縮表示を優先。
選択中 theme_id・seed・latest outputs を参照。成果物がなければ短い案内のみ（raw パス・run_id は通常非表示）。

## サイドバーの次アクション

本番実行モードでは seed / Manual Claims / Evidence Map / Paper/Web / Link/Watch/Digest / Final Validation の進捗を表示し、不足に応じて次アクションを 1 行で示す（例: seed がなければ「seed 公報を入力してください」）。

## 外部 API 注意の扱い

利用上の注意は Phase 24.5A の「はじめる」タブに集約。本番実行では外部 API 実行ボタン付近のみ短い注意と明示同意チェックボックスを残す。

## 禁止事項（本 Phase でも変更しない）

分析アルゴリズム変更、OpenAlex/Tavily/BigQuery 自動実行、UI からのメール送信・ scheduler 登録、Cloud Run/SQL/Gmail/OAuth/DB 追加、FTO・侵害・有効性判断、API キー hardcode、high confidence 自動付与
