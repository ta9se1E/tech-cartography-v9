# v9 Credential Rotation Manual Steps

This runbook covers Stage B only. Do not paste secret values into chat, tickets, or git.

## Scope

- v9 Cloud Run weekly Job secrets: SMTP and Tavily
- Local `.env` entries used by v9 development
- No v7/v8 asset changes
- Scheduler remains PAUSED until explicitly approved later

## Credential Summary

| Credential | Current use | Stage B action |
|---|---|---|
| SMTP_PASSWORD | Cloud Run Job + local email delivery | Rotate cloud + local |
| TAVILY_API_KEY | Cloud Run Job + local web retrieval | Rotate cloud + local |
| OPENAI_API_KEY | Not used by v9 Cloud Runtime | Revoke provider key, remove from local `.env` |
| OPENALEX_API_KEY | Not used by v9 OpenAlex provider | Revoke provider key, remove from local `.env` |
| LANGCHAIN_API_KEY | Local LangChain tracing only | Rotate locally if still needed |
| LANGSMITH_API_KEY | Local LangSmith tracing only | Rotate locally if still needed |
| TECH_CARTOGRAPHY_LOGIN_PASSWORD | Not used by v9 IAP Service | Remove from local `.env`; do not create a new password unless a separate local-only login flow is restored |

LangChain and LangSmith are separate credentials in the current inventory. Do not create two new provider keys if only one tracing stack is actually used.

## Stage B Execution Order

1. Issue new credentials in each provider admin console.
2. Keep old credentials enabled until Stage B verification succeeds.
3. Run the secure helper with hidden terminal input:

```bash
V9_CREDENTIAL_ROTATION_APPROVED=true \
  python scripts/rotate_v9_credentials_secure.py --apply
```

4. Confirm the helper reports new Secret Manager version numbers only.
5. Pin Cloud Run Job secrets to numeric versions:

```text
SMTP_PASSWORD=tech-cartography-smtp-password:<NEW_NUMERIC_VERSION>
TAVILY_API_KEY=tech-cartography-tavily-api-key:<NEW_NUMERIC_VERSION>
```

6. Keep the clean image digest and all safety env settings unchanged:
   - providers disabled
   - `V9_CLOUD_JOB_DRY_RUN=true`
   - email disabled
   - Scheduler PAUSED
7. Confirm Job Ready with providers still disabled.
8. Run minimal Tavily connectivity test:
   - one approved query
   - max 1 result
   - Google Grounding=false
   - BigQuery=false
   - OpenAlex=false
9. Run minimal SMTP test:
   - one self-addressed message
   - reuse existing successful digest artifact
   - duplicate-send guard must remain active
10. For any other credential still classified active, run the smallest auth-only check available.
11. After all checks pass, revoke old provider credentials.
12. Disable old Secret Manager versions. Do not destroy them in Stage B.
13. Leave Scheduler PAUSED.

## Provider Issuance Locations (types only)

| Credential | Issuance location type |
|---|---|
| SMTP_PASSWORD | Email provider account security / App Password settings |
| TAVILY_API_KEY | Tavily developer dashboard API key page |
| OPENAI_API_KEY | OpenAI platform API key page (revoke only if removing) |
| OPENALEX_API_KEY | OpenAlex account settings if a key exists (revoke only if removing) |
| LANGCHAIN_API_KEY | LangChain/LangSmith workspace API key page |
| LANGSMITH_API_KEY | LangSmith workspace API key page |
| TECH_CARTOGRAPHY_LOGIN_PASSWORD | No new password unless local-only login is intentionally restored |

## Old Credential Retirement Order

1. Verify new Secret Manager versions exist.
2. Pin Job to numeric versions and confirm Ready.
3. Pass Tavily minimal connectivity test.
4. Pass SMTP self-send test.
5. Revoke old provider credentials.
6. Disable old Secret Manager versions.
7. Remove unused local `.env` entries for revoked credentials.

## Rollback

If Stage B verification fails before provider revocation:

1. Re-pin Job secrets to the previous enabled Secret Manager version numbers.
2. Confirm Job Ready with providers disabled.
3. Restore previous local `.env` values manually through the secure helper or hidden terminal editing.
4. Leave old provider credentials enabled.
5. Leave Scheduler PAUSED.
6. Do not disable old Secret Manager versions until a successful re-test on the previous versions.

## Explicitly Out of Scope for Stage B Start

- Scheduler resume
- weekly delivery `enabled=true`
- BigQuery production queries
- automatic weekly operations
- git push
- final release tag creation
