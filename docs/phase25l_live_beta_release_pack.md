# Phase 25L — Live Beta Release Pack and Stakeholder Handoff

## Phase 25K との差分

| Phase | 内容 |
|-------|------|
| 25K | Live 成果物7ステップの手動週次運用コンソール + `live_operation_status` 保存 |
| **25L** | **関係者向け Live Beta Release Pack（共有用）の生成・保存・UI** |

## なぜ Release Pack が必要か

Phase 25E〜25K で Live 上の手動運用ループは揃いましたが、職場の仲間・上司・関係者へ説明する際は、

- 現在のサービス状態
- 使い方と安全範囲
- 既知の制限
- デモ手順
- 共有文面

を **1つのパック** として渡す必要があります。Release Pack は新しい外部 API ではなく、**既存 Live 成果物と運用状態の handoff 用エクスポート** です。

## 共有パックの構成

保存先: `LIVE_OUTPUTS_ROOT/live_release_pack/`（未設定時は `outputs/live_release_pack/`）

| ファイル | 内容 |
|----------|------|
| `live_beta_release_pack_<timestamp>.json` | 構造化メタデータ |
| `live_beta_release_pack_<timestamp>.md` | 人間向け Markdown |
| `live_beta_release_pack_<timestamp>.txt` | テキスト要約 |
| `live_beta_release_pack_<timestamp>.zip` | 関係者配布用（README + 主要 txt + json） |

zip 内:

- `README.md`
- `demo_script_3min.txt`
- `stakeholder_share_message.txt`
- `known_limitations_and_scope.txt`
- `admin_operation_checklist.txt`
- `release_pack.json`

## 入力ソース

- latest `live_operation_status`（なければ missing）
- latest digest preview / watch profile draft / next cycle search plan の要約
- artifact counts（`describe_live_artifact_storage`）
- runtime flags（外部 API / email / scheduler）
- optional release note

## 共有時の注意

- **限定公開** として扱う
- Web Signal は **確認候補** であり事実確定ではない
- FTO・侵害・有効性判断は行わない
- 研究開発・技術探索の **補助** であることを明記する

## secret を含めない方針

Release Pack および zip には以下を **含めません**:

- ログインパスワード
- API キー
- SMTP 設定値
- 送信先メールの大量リスト
- メール本文全文
- 生の secret 値

保存前に sensitive pattern と env 値リークチェックを行います。

## Live Beta の安全範囲

- scheduler **OFF**
- メール **self_only** のみ
- 外部 API **通常 OFF**（手動 smoke / pack 作成時のみ一時 ON 可）
- **手動運用**（自動週次実行なし）
- 本番導入前には認証強化・監査ログ・権限管理が必要

## UI

- **レポートタブ**（`v7_easy_app`）: admin expander「Live Beta Release Pack（共有用）」
- **設定タブ**（`user_settings_view`）: 同上
- 表示条件: `REQUIRE_LOGIN=true` かつ `role=admin`
- operation status 未保存時は Live Operation Console への案内を表示

## 次 Phase で進む候補

- CI/CD
- Google login / IAP
- 関係者向け閲覧権限
- 承認付きメンバー送信
