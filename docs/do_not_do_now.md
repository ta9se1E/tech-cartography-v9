# Do Not Do Now (v7)

The following are explicitly out of scope for the current v7 phases:

- Monthly / biweekly evidence map update automation
- Email delivery of reports
- Cloud Run deployment
- Cloud SQL integration
- Cloud Scheduler jobs
- v6 weekly-watch baseline bulk copy

Current focus through Phase 11:

- Phase 1: Search Strategy Builder
- Phase 2: BigQuery light metadata retrieval
- Phase 3: Technology clustering / ranking
- Phase 4: Top5 full text evidence collection
- Phase 5: Claim element extraction
- Phase 6: OpenAlex paper evidence search
- Phase 7: Patent Claim × Paper Evidence Map
- Phase 8: Technical View Agent
- Phase 9: Web / Company Signal Mapping (manual input)
- Phase 10: Business View Agent
- Phase 11: Synthesis Report

Phase 11 produces the integrated Carbon Fiber Evidence Map report but does **not** automate periodic updates, email delivery, or cloud deployment yet.

Phase 12 adds a one-command pipeline runner but still does **not** add:

- Monthly / biweekly automatic updates
- Email sending
- Cloud Run / Cloud SQL / Scheduler
- Automatic web search (Tavily, etc.)

Phase 13 improves ranking quality and Japanese UI but still does **not** add:

- Automatic web search (Tavily, etc.)
- Cloud Run / Cloud SQL / Scheduler
- Email sending
- Scope remains: ranking quality + easy Japanese UI (no new external APIs)

Phase 13.1 clarifies:

- Chinese patents are **not** excluded — they appear in Strategic Watch Candidates
- Top5 Fulltext Candidates prioritize US retrieval feasibility, not global strategic importance
- Non-US important patents are tracked via Strategic Watch Candidates (manual/PDF route)

Phase 14 adds Controlled Full Text Run but still does **not** add:

- Automatic PDF download
- OCR
- Automatic web search (Tavily, etc.)
- Scope: US Top5 controlled fulltext + manual watch package for CN/EP/JP
