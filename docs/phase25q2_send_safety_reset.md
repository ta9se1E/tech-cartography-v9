# Phase 25Q.2 — Send Safety Reset and Operation Guard

## 目的

承認済みメンバーへの Digest 手動送信テストが成功した後も、メール送信 env が ON のまま残ると誤送信リスクがあります。
本 Phase では送信状態の見える化・安全復帰手順・運用ガードを追加し、**テスト後に OFF へ戻す**運用を支援します。

- Scheduler・一斉送信・自動送信は **実装しません**
- アプリから Cloud Run env を変更しません（gcloud は手動）

## なぜ送信後に OFF へ戻すか

| リスク | 説明 |
|--------|------|
| 誤操作 | UI から再度手動送信できる状態が続く |
| 設定残存 | `TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS` が本番に残る |
| 監査 | 「いつ送信可能だったか」が不明瞭になる |

デフォルト deploy は常に `DISABLE_EMAIL_SEND=true`, `ENABLE_APPROVED_MEMBER_SEND=false` です。

## safety_level 一覧

| level | 条件（概要） | 意味 |
|-------|-------------|------|
| `safe_off` | `DISABLE_EMAIL_SEND=true` かつ `ENABLE_APPROVED_MEMBER_SEND=false` | 安全（送信停止） |
| `controlled_manual_send_enabled` | 送信ON + 承認メンバーあり + scheduler OFF + SMTP OK | 制御付き手動送信（テスト中） |
| `risky_email_enabled` | 送信ON + scheduler ON など | 要注意 |
| `misconfigured` | 送信ON だが SMTP 不足 or 承認リスト空 | 設定不足 |

## 本番テスト手順

### 送信前チェックリスト

- [ ] IAP admin でログイン済み
- [ ] `AUTH_PROVIDER_MODE=iap`
- [ ] Digest Preview 作成済み
- [ ] `ENABLE_APPROVED_MEMBER_SEND=true`
- [ ] `DISABLE_EMAIL_SEND=false`
- [ ] `TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS` にテスト宛先のみ
- [ ] `DISABLE_SCHEDULER=true`
- [ ] SMTP 設定 + Secret Manager `SMTP_PASSWORD`
- [ ] UI の「メール送信 運用状態」が `controlled_manual_send_enabled`

### 送信後チェックリスト

- [ ] Run History: `action_type=live_approved_member_email_send`, `status=success`
- [ ] artifact: `outputs/live_approved_member_send/*.json` に `reset_required=true`
- [ ] 実メール受信確認
- [ ] **必ず** 下記コマンドで OFF に戻す

## OFF へ戻すコマンド

```bash
PROJECT_ID=devops-ai-agent-hackathon-2026
REGION=us-central1
SERVICE=tech-cartography-v7-live

gcloud run services update "$SERVICE" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --update-env-vars "ENABLE_APPROVED_MEMBER_SEND=false,DISABLE_EMAIL_SEND=true" \
  --remove-env-vars TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS,EMAIL_RECIPIENT_ALLOWLIST
```

**secret は含めません。** 実行はターミナルで手動。

## artifact 確認

成功送信ログ（`live_approved_member_send_*.json`）に含まれる項目:

- `post_send_recommended_action`: `disable_email_send`
- `post_send_safety_note`
- `reset_required`: `true`
- `reset_command_hint`（secret なし gcloud コマンド）
- `scheduler_state_at_send`
- `disable_email_send_at_send`
- `approved_member_send_enabled_at_send`

## Run History 確認

`run_history_*.json` の `operation_metadata`:

- `post_send_recommended_action=disable_email_send`
- `reset_required=true`
- `recipient_masked`
- `recipient_domain`

## Scheduler とは別

本機能は **手動・1通・承認済みメンバー限定** です。週次自動送信（scheduler）とは独立しています。

## 一斉送信ではない

selectbox で 1 宛先のみ。全員一斉送信 UI はありません。

## secret を扱わない

- UI / artifact / Run History に SMTP_PASSWORD・OAuth・JWT を表示・保存しません
- `smtp_password_configured` は bool のみ
