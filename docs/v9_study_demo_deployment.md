# Tech Cartography v9 Study Demo Deployment Record

## Summary

| Item | Value |
|------|-------|
| Deployed at (UTC) | 2026-07-04T19:28:07Z |
| Deployed at (JST) | 2026-07-05 04:28:07 JST |
| Expires at (UTC) | 2026-07-11T19:27:30Z |
| Expires at (JST) | 2026-07-12 04:27:30 JST |
| Service | `tech-cartography-v9-study-demo` |
| Service URL | https://tech-cartography-v9-study-demo-utejl5os5a-uc.a.run.app |
| Revision | `tech-cartography-v9-study-demo-00001-b48` |
| Image digest | `sha256:8233e7a1741d9a83eadf0ff9e6250cabbd6f444aeb127443e2b1d71696ad49a4` |
| Image URI | `us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/cloud-run-source-deploy/tech-cartography-v9-study-demo:c560647` |
| Service Account | `tech-cartography-v9-study-demo@devops-ai-agent-hackathon-2026.iam.gserviceaccount.com` |
| Bucket | `tech-cartography-v9-study-demo-1020686343587` |
| Password secret | `tech-cartography-v9-study-demo-password:1` |
| Min / max instances | 0 / 1 |
| Public method | `allUsers` → `roles/run.invoker` |
| Cloud Build ID | `d313da83-1e79-49b5-96a7-d44e40d4cc7e` |

## Isolation controls

- External providers disabled: BigQuery, OpenAlex, Tavily, Google Grounding
- Email disabled (`EMAIL_SEND_MODE=preview`, `V9_ENABLE_EMAIL_SEND=false`)
- No Cloud Run Job
- No Cloud Scheduler
- No SMTP / Tavily secret mounts
- Demo bucket mounted at `/mnt/v9_study_demo`; active data under `active/`

## Seed data

| Item | Value |
|------|-------|
| Source run ID | `cloud_weekly_job_20260704_181253` |
| Source bucket (read-only) | `tech-cartography-v9-weekly-persist-1020686343587` |
| Seed object count | 10 |
| Active object count | 9 |
| Sanitize validation | passed (metadata-only checks) |

## Production unchanged (verified)

- Service `tech-cartography-v9-signal-watch` revision `00003-br7`, IAP enabled
- Job production config maintained
- Scheduler `ENABLED` (`0 9 * * 1`, `Asia/Tokyo`)
- Weekly delivery `enabled=true`

## Cleanup (after study week)

```bash
cd /path/to/PatentScout_AI_v9_study_demo
bash scripts/cleanup_v9_study_demo.sh --plan
V9_STUDY_DEMO_CLEANUP_APPROVED=true bash scripts/cleanup_v9_study_demo.sh --apply
```

Do not modify production resources during cleanup.

## Browser Acceptance Validation

Validation status:
PASSED

Validated by:
User

Validation date:
2026-07-05 04:40:00 JST

Validated items:

- Public URLからpassword gateを表示できた
- ログイン前は6タブとデータを表示しなかった
- 誤ったパスワードではログインできなかった
- 正しい共通パスワードでログインできた
- 6タブを正常に表示できた
- 勉強会用バナーを表示できた
- 保存済み実データを表示できた
- 外部検索停止の案内を確認できた
- メール送信停止の案内を確認できた
- ログアウト後にpassword gateへ戻った
- ブラウザ上のエラーはなかった

Acceptance conclusion:
The isolated study demo is ready for the study session.

Expiry:
2026-07-12 04:27:30 JST
