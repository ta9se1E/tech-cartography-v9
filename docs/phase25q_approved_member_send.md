# Phase 25Q — Approved Member Digest Send

## 目的

Phase 25G の **self-only 送信** に加え、管理者が事前承認済みのメンバーへ、手動確認後に **1通ずつ** Digest Preview を送信できる安全な機能を追加する。

- 一斉送信・自由入力送信・scheduler 送信は **実装しない**
- デフォルトは **無効**（deploy しても勝手に有効化しない）

## self-only send との違い

| 項目 | Phase 25G (self-only) | Phase 25Q (approved member) |
|------|----------------------|----------------------------|
| 送信先 | 自分（allowlist 内） | **事前承認済みメンバー**（env 一覧のみ） |
| 宛先入力 | text_input（allowlist 検証） | **selectbox**（自由入力不可） |
| 有効化フラグ | `EMAIL_SEND_MODE=self_only` | `ENABLE_APPROVED_MEMBER_SEND=true` |
| 確認テキスト | `SEND TO MYSELF` | `SEND TO APPROVED MEMBER` |
| 操作権限 | admin | admin のみ（member は不可） |

## 安全設計

1. **デフォルト無効** — `ENABLE_APPROVED_MEMBER_SEND=false`
2. **メール送信マスター停止** — `DISABLE_EMAIL_SEND=true` なら絶対に送信しない
3. **承認リストのみ** — `TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS` に含まれる宛先だけ
4. **1通・1宛先** — CC/BCC・複数宛先・一斉送信なし
5. **手動のみ** — scheduler / 自動週次送信なし
6. **確認テキスト必須** — `SEND TO APPROVED MEMBER` の完全一致
7. **secret 非保存** — SMTP_PASSWORD / OAuth / JWT は artifact・Run History に残さない
8. **メール本文** — FTO/侵害/有効性判断を含めない。Web Signal は候補情報である旨を明記

## 環境変数

| 変数 | デフォルト | 説明 |
|------|-----------|------|
| `ENABLE_APPROVED_MEMBER_SEND` | `false` | `true` のときのみ機能表示・送信可能 |
| `TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS` | （空） | カンマ区切り承認済みメール。空なら送信不可 |
| `APPROVED_MEMBER_SEND_CONFIRMATION` | `SEND TO APPROVED MEMBER` | 確認テキスト（変更可） |
| `DISABLE_EMAIL_SEND` | `true`（live デフォルト） | `true` なら送信不可 |
| `SMTP_*` / `SMTP_PASSWORD` | — | 既存 Secret Manager 参照（Phase 25G 同様） |

## 有効化手順

Cloud Run live で明示的に env を更新してください。**cloudbuild.yaml にメールアドレスは直書きしません。**

```bash
PROJECT_ID=devops-ai-agent-hackathon-2026
REGION=us-central1
SERVICE=tech-cartography-v7-live

gcloud run services update "$SERVICE" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --update-env-vars \
ENABLE_APPROVED_MEMBER_SEND=true,\
DISABLE_EMAIL_SEND=false,\
TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS=approved@example.com
```

複数宛先はカンマ区切り:

```bash
--update-env-vars TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS=approved01@example.com,approved02@example.com
```

SMTP は Phase 25G と同様に Secret Manager 経由で `SMTP_PASSWORD` を設定済みであること。

## 無効化手順

```bash
gcloud run services update "$SERVICE" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --update-env-vars \
ENABLE_APPROVED_MEMBER_SEND=false,\
DISABLE_EMAIL_SEND=true,\
TECH_CARTOGRAPHY_APPROVED_MEMBER_EMAILS=
```

## 確認文

UI で次の文字列を **完全一致** で入力しないと送信ボタンは有効になりません:

```
SEND TO APPROVED MEMBER
```

環境変数 `APPROVED_MEMBER_SEND_CONFIRMATION` で変更可能です。

## 送信ログ / Run History 確認

### 送信ログ（artifact）

保存先: `outputs/live_approved_member_send/`

| ファイル | 内容 |
|----------|------|
| `live_approved_member_send_<timestamp>.json` | timestamp, run_id, action_type, status, user_id, recipient_email, digest_preview_artifact, safety_flags など |
| `live_approved_member_send_<timestamp>.md` | 同上（人間可読） |

`action_type=live_approved_member_email_send`

### Run History

`outputs/live_run_history/run_history_*.json` に記録されます。

- `action_type`: `live_approved_member_email_send`
- `user_id`: IAP メールアドレス
- `input_summary`: マスク済み recipient / domain
- `output_artifact_paths`: 上記 json/md

## 禁止事項

- 一斉送信
- 自由入力メール送信
- scheduler 連携 / 自動週次送信
- member による他者宛送信
- 未承認メールへの送信
- secret / OAuth / JWT / SMTP_PASSWORD の保存・表示
- FTO/侵害/有効性判断をメール本文に含める

## rollback 手順

承認済みメンバー送信を止める場合は **無効化手順** を実行してください。

IAP → Basic への切り戻しが必要な場合は `scripts/rollback_live_to_basic.sh` を使用します（`ENABLE_APPROVED_MEMBER_SEND=false` を含む）。

## scheduler とは別機能

本機能は **手動・1通・承認済みメンバー限定** です。`DISABLE_SCHEDULER=true` のまま運用し、週次自動送信とは独立しています。

## 一斉送信ではない

UI は selectbox で **1アドレス** を選び、ボタン1回で **1通** のみ送信します。全員への一斉送信 UI はありません。
