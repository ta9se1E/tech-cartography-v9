# Phase 25F — Live Digest Mail Preview

## 目的

Phase 25E の **Live Web Signal Pack** を材料に、職場メンバー共有用の **週次 Digest メール下書きプレビュー** を作成する。

**実メール送信は行いません。**

## Phase 25E との差分

| Phase 25E | Phase 25F |
|-----------|-----------|
| Tavily → Web Signal candidate pack | pack → Digest メール下書き preview |
| 企業・市場シグナルタブに candidates 表示 | レポートタブに Digest preview 表示 |
| 外部 API 呼び出しあり | **Tavily を新たに呼ばない**（既存 pack を読むのみ） |

## 流れ

1. admin が Live Web Signal Pack を作成（Phase 25E）
2. latest `outputs/live_web_signals/live_web_signal_pack_*.json` を検出
3. 「メール下書きを作成」で preview 生成
4. `outputs/live_digest_preview/` に json / md / txt 保存
5. レポートタブで最新 preview を参照

## 実メール送信はまだしない

- Gmail API / SMTP / SendGrid 等は **呼ばない**
- UI に送信ボタンは **ない**
- `DISABLE_EMAIL_SEND=true` でも **preview 作成は可能**
- preview は下書きであり、送信ログではない

## `DISABLE_EMAIL_SEND=true` の意味

| 機能 | 挙動 |
|------|------|
| Digest preview 作成 | **可能** |
| 実メール送信 | **不可**（Phase 25F では UI も実装しない） |

## 保存ファイル仕様

保存先: `outputs/live_digest_preview/`

| ファイル | 内容 |
|----------|------|
| `live_digest_preview_<timestamp>.json` | source_pack_path, theme_name, subject, body, key_signals, next_actions, safety_notice, created_at |
| `live_digest_preview_<timestamp>.md` | markdown body |
| `live_digest_preview_<timestamp>.txt` | plain text body |

**API キー・大量メールアドレスリストは含めない**

## メール本文構成

- 件名（subject）
- 今週の確認対象テーマ
- 注目 Web Signal 候補（最大3件）+ なぜ確認すべきか
- 注意点 / Evidence Gaps
- 次アクション
- 免責（Web Signal は確認候補、FTO/侵害/有効性判断ではない）

## Safety notice

> These Web Signals are review candidates only. They do not prove direct relationship, market truth, legal status, infringement, or validity. Primary-source verification is required before any decision.

## UI

### 入力・実行タブ（admin）

- expander: **Live Digest Mail Preview（送信なし）**
- latest pack 検出 / theme_name 表示
- recipient_group_name / user_note
- 「メール下書きを作成」ボタン
- **「これは送信されません」** を明記

### レポートタブ（analyst/live）

- expander: **Live Digest Preview（送信なし）**
- demo mode では表示しない

## 次 Phase

- 自分宛てテスト送信（SMTP 等）への段階的移行を予定
- その前に preview 品質と safety notice を職場内で確認

## 関連モジュール

- `src/tech_cartography/services/live_digest_preview.py`
- `src/tech_cartography/ui/live_digest_preview_ui.py`
