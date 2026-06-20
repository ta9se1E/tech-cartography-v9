# Phase 24.2 — Manual Weekly Digest Test Email

## 目的

Phase 24.1 / 24.1.1 で整備した Weekly Digest / Email Draft / Email Outbox を使い、**CLI の明示操作のみ**でテストメール送信を行えるようにします。

- UI からは送信しない
- `--send-email` がない限り送信しない
- 送信前に必ず Email Draft を Outbox に保存
- 送信ログを `outputs/delivery/email_send_logs/` に記録

## 宛先設定ファイル

1. 例をコピー:

```bash
cp config/email_recipients.example.json config/email_recipients.json
```

2. `config/email_recipients.json` を編集（**このファイルは .gitignore 対象**）

```json
{
  "internal_review": {
    "to": ["your-address@example.com"],
    "cc": [],
    "enabled": true,
    "note": "Internal review only"
  }
}
```

### enabled=false がデフォルトの理由

誤送信を防ぐため、example および初期状態は `enabled=false` です。宛先を確認したうえで `enabled=true` にしてください。

## 役割分担

| ツール | 役割 |
|--------|------|
| `build_delivery_package.py` | Digest / Report / Draft を**作る** |
| `send_weekly_digest_test.py` | 宛先を解決し、**送信テスト**する |

## dry-run

```bash
python scripts/send_weekly_digest_test.py \
  --publication-number US-12565719-B2 \
  --recipient-config config/email_recipients.example.json \
  --recipient-group default \
  --dry-run
```

- 送信しない
- 宛先設定の検証結果を send log に記録

## draft 作成のみ

```bash
python scripts/send_weekly_digest_test.py \
  --publication-number US-12565719-B2 \
  --recipient-config config/email_recipients.json \
  --recipient-group internal_review \
  --build-draft
```

- `enabled=true` かつ有効な `to` が必要
- Outbox に draft を保存
- send log に `draft_saved` を記録

## 明示送信

```bash
python scripts/send_weekly_digest_test.py \
  --publication-number US-12565719-B2 \
  --recipient-config config/email_recipients.json \
  --recipient-group internal_review \
  --build-draft \
  --send-email
```

前提:

- `config/email_recipients.json` で `enabled=true`
- SMTP 環境変数がすべて設定済み

## SMTP 環境変数

```
TC_SMTP_HOST
TC_SMTP_PORT
TC_SMTP_USER
TC_SMTP_PASSWORD
TC_SMTP_FROM
```

**注意**: `TC_SMTP_PASSWORD` の値はログ・JSON 出力に保存しません。

## 送信ログ

保存先: `outputs/delivery/email_send_logs/`

| ファイル | 内容 |
|---------|------|
| `send_log_{timestamp}_{pub}.json` | 個別ログ |
| `send_log_latest_{pub}.json` | 最新ログ |
| `send_log_index.json` | 直近50件のインデックス |

status 例:

- `dry_run`
- `draft_saved`
- `sent`
- `blocked_missing_recipient`
- `blocked_recipient_disabled`
- `blocked_missing_adapter`
- `failed`

## UI

レポートタブに **送信ログ（参照のみ）** を表示します。送信ボタンはありません。

> UIからのメール送信は無効です。送信する場合はCLIで --send-email を明示してください。

## 注意事項

- FTO / 侵害 / 有効性判断ではありません
- Webシグナルは確認候補です
- high confidence の自動付与なし
- Gmail API / OAuth / スケジューラーはこの Phase では未実装
