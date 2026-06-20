# Phase 24.3 — Weekly Digest Local Scheduling

## 目的

Phase 24.2 / 24.2.1 で確立した手動メール送信を、ローカルMac環境で週次実行できるようにします。

ただし、いきなり完全自動送信にせず、以下の安全設計を守ります。

- デフォルトは **draft-only**（下書き作成のみ）
- 実送信は `--send-email` を明示した場合のみ
- スケジュール登録は `--install --yes` を明示した場合のみ
- UIから送信・登録しない

## ローカル週次実行の考え方

| ツール | 役割 |
|--------|------|
| `run_weekly_digest_job.py` | 週次ジョブ本体（draft / send / dry-run） |
| `install_weekly_digest_schedule.py` | launchd plist / wrapper / cron sample 生成 |
| `run_weekly_digest_job.sh` | launchd から呼ぶ wrapper（`.env` を source） |

## なぜ wrapper script で `.env` を source するのか

launchd は通常、シェルの profile や `.env` を自動読み込みしません。
そのため Python を直接呼ばず、bash wrapper で以下を行います。

```bash
cd "$PROJECT_DIR"
set -a && source .env && set +a
"$PYTHON_BIN" scripts/run_weekly_digest_job.py ...
```

SMTP_PASSWORD などの秘密情報は wrapper に書きません。

## draft-only 運用（推奨デフォルト）

```bash
set -a && source .env && set +a

python scripts/run_weekly_digest_job.py \
  --publication-number US-12565719-B2 \
  --recipient-config config/email_recipients.json \
  --recipient-group internal_review \
  --build-draft
```

- Outbox に下書き保存
- send log: `draft_saved`
- job log: `outputs/delivery/job_logs/`

## send-enabled 運用

```bash
python scripts/run_weekly_digest_job.py \
  --publication-number US-12565719-B2 \
  --recipient-config config/email_recipients.json \
  --recipient-group internal_review \
  --build-draft \
  --send-email
```

同一週に既に `sent` がある場合は `skipped_already_sent_this_week`（`--allow-repeat-this-week` で解除可）。

## スケジューラーファイル生成

```bash
python scripts/install_weekly_digest_schedule.py \
  --publication-number US-12565719-B2 \
  --recipient-config config/email_recipients.json \
  --recipient-group internal_review \
  --weekday 1 \
  --hour 8 \
  --minute 30 \
  --python-bin /opt/miniconda3/envs/2026hack/bin/python
```

出力先: `outputs/delivery/scheduler/`

- `com.techcartography.weeklydigest.plist`
- `run_weekly_digest_job.sh`
- `weekly_digest_cron_sample.txt`
- `scheduler_readme.md`

送信ONの設定ファイル生成:

```bash
python scripts/install_weekly_digest_schedule.py \
  ... \
  --enable-send
```

## launchd 登録

```bash
python scripts/install_weekly_digest_schedule.py \
  --publication-number US-12565719-B2 \
  --recipient-config config/email_recipients.json \
  --recipient-group internal_review \
  --weekday 1 --hour 8 --minute 30 \
  --install --yes
```

`--install` だけでは登録しません。`--yes` も必要です。

## launchd 解除

環境によりコマンドが異なる場合があります。

```bash
launchctl unload ~/Library/LaunchAgents/com.techcartography.weeklydigest.plist
```

## cron sample

`weekly_digest_cron_sample.txt` に月曜 8:30 の例が入ります（draft-only デフォルト）。

## 同一週の重複送信防止

- `should_skip_already_sent_this_week()` が send log index を参照
- `created_at` を Asia/Tokyo に変換し ISO週で判定
- `allow_repeat_this_week=False`（デフォルト）なら skip

## 送信ログ・ジョブログ

| 種別 | 保存先 |
|------|--------|
| send log | `outputs/delivery/email_send_logs/` |
| job log | `outputs/delivery/job_logs/` |
| scheduler log | `outputs/delivery/scheduler_logs/` |

失敗時も job log を残し、次回実行可能です。

## UIから登録しない理由

誤送信・誤登録を防ぐため、スケジュール登録は CLI の明示操作のみとします。
UIには説明と生成ファイルの参照・ダウンロードのみ表示します。

## Cloud Run / Cloud Scheduler を今回やらない理由

ローカルMacでの週次運用を先に安定させるためです。
クラウド実行は別 Phase で検討します。

## トラブルシュート

| 症状 | 確認 |
|------|------|
| SMTP blocked | `source .env` 後に `SMTP_*` が入っているか |
| skipped | 今週既に sent がある。`--allow-repeat-this-week` で再送可 |
| launchctl 失敗 | `~/Library/LaunchAgents/` の plist パス、macOS バージョン差 |
| wrapper 失敗 | `bash outputs/delivery/scheduler/run_weekly_digest_job.sh` を手動実行 |

## 禁止事項（この Phase）

- Cloud Run / Cloud Scheduler
- Gmail API / OAuth
- UIからの実送信・スケジュール登録
- 新規 Tavily / BigQuery / OpenAlex 実行
