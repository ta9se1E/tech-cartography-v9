# Phase 25G — Self-only Live Digest Email Send Test

## 目的

Phase 25F の **Live Digest Preview** を材料に、admin が明示確認した場合に限り **自分宛て1通だけ** SMTP テスト送信する。

- 一斉送信・自動送信・scheduler 連携は **まだ行わない**

## Phase 25F との差分

| Phase 25F | Phase 25G |
|-----------|-----------|
| preview 作成・保存のみ | **self_only SMTP 送信（1通）** |
| 送信ボタンなし | 確認テキスト + 自分宛て送信ボタン |
| `DISABLE_EMAIL_SEND=true` でも preview 可 | 送信は `DISABLE_EMAIL_SEND=false` 時のみ |

## self_only 送信の意味

- `EMAIL_SEND_MODE=self_only` のときだけ送信可能
- recipient は `EMAIL_RECIPIENT_ALLOWLIST` に含まれる **1アドレスのみ**
- cc/bcc・複数宛先・一斉送信は **不可**
- UI 確認テキスト `SEND TO MYSELF` の完全一致が必要

## 環境変数

| 変数 | 説明 |
|------|------|
| `DISABLE_EMAIL_SEND` | `true` なら **絶対に送信しない** |
| `EMAIL_SEND_MODE` | `self_only` のみ送信許可 |
| `EMAIL_SENDER` | From アドレス（未設定時は SMTP_USERNAME） |
| `EMAIL_RECIPIENT_ALLOWLIST` | カンマ区切り許可宛先 |
| `SMTP_HOST` | SMTP サーバー |
| `SMTP_PORT` | `465`（SSL）または `587`（STARTTLS） |
| `SMTP_USERNAME` | SMTP ユーザー |
| `SMTP_PASSWORD` | SMTP パスワード — **Secret Manager 推奨** |

## SMTP_PASSWORD は Secret Manager で渡す

```bash
echo -n "YOUR_SMTP_PASSWORD" | gcloud secrets create tech-cartography-smtp-password \
  --data-file=- \
  --replication-policy=automatic
```

**実パスワードを docs / git / 画面 / ログに書かないでください。**

## Cloud Run live 設定例

**注意:** `--set-env-vars` は既存 env を上書きするため、ログイン情報を消さないよう **`--update-env-vars` / `--update-secrets`** を使ってください。

```bash
gcloud run services update tech-cartography-v7-live \
  --region us-central1 \
  --update-env-vars \
DISABLE_EMAIL_SEND=false,\
EMAIL_SEND_MODE=self_only,\
EMAIL_SENDER=you@example.com,\
EMAIL_RECIPIENT_ALLOWLIST=you@example.com,\
SMTP_HOST=smtp.example.com,\
SMTP_PORT=465,\
SMTP_USERNAME=you@example.com \
  --update-secrets SMTP_PASSWORD=tech-cartography-smtp-password:latest
```

demo サービスは `DISABLE_EMAIL_SEND=true` のまま維持してください。

## `DISABLE_EMAIL_SEND` の意味

| 値 | preview 作成 | self_only 送信 |
|----|-------------|----------------|
| `true` | 可能 | **不可** |
| `false` + `EMAIL_SEND_MODE=self_only` + allowlist + SMTP | 可能 | 可能（admin + 確認テキスト） |

## 送信ログ仕様

保存先: `outputs/live_email_send/`

| ファイル | 内容 |
|----------|------|
| `live_email_send_<timestamp>.json` | sent_at, recipient_masked, subject, preview_source_path, provider, send_mode, result_status, safety_notice |
| `live_email_send_<timestamp>.md` | 同上（Markdown） |

**送信成功時のみ** ログ保存。SMTP_PASSWORD・API キー・本文全文は含めません。

## Safety notice（送信本文・UI）

- Live Digest Preview のテスト送信であること
- Web Signal は確認候補であり確定事実ではない
- FTO / 侵害 / 有効性判断ではない
- 原典確認が必要

## UI

- **入力・実行タブ** — expander「Self-only Email Send Test（自分宛てのみ）」
- **レポートタブ** — Live Digest Preview の下（demo mode では非表示）

## 次 Phase

- 承認付きメンバー送信（allowlist 拡張 + 監査ログ）への段階的移行を予定

## 関連モジュール

- `src/tech_cartography/runtime/email_send_config.py`
- `src/tech_cartography/services/live_email_sender.py`
- `src/tech_cartography/ui/live_email_send_ui.py`
