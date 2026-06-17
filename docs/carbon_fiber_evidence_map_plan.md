# Carbon Fiber Evidence Map Plan

## Roadmap

### Step 1: Search Strategy Builder

- Build `SearchProfile` from user input or demo YAML
- Analyze optional seed patents with `SeedPatentAnalyzer`
- Generate intent-specific `QueryPlan` objects for carbon fiber evidence mapping
- Recommend `core_manufacturing` as the first plan
- No BigQuery execution in this step

### Step 2: BigQuery Light Multi-Query Retrieval

- Use multiple `query_plan` objects from Search Strategy Builder
- Run intent-specific lightweight BigQuery retrieval
- Retrieve up to ~2,000 metadata records total
- Do not fetch full text, claims, or description
- Top5 full-text collection is a later phase
- Attach `search_intent`, `query_plan_id`, and `matched_terms` to every record
- Deduplicate by `publication_number` before export

### Step 3: AI Technology Clustering & Patent Ranking

- Input: Phase 2 `bigquery_light_results_dedup.csv`
- Rule-based technology classification into carbon fiber clusters
- Noise scoring without automatic deletion
- Rank patents and select Top20 important patents
- Select Top5 full-text fetch candidates (metadata stage only)
- Export classified/ranked CSV and `carbon_fiber_evidence_map_report.md`
- LLM classification remains optional for future extension

### Step 4: Top5 Full Text Evidence Collection

- Input: `top5_fulltext_candidates.csv` from Phase 3
- US route: BigQuery full text dry-run / execute with cost guard and cache
- Non-US route: manual full text upload path
- Extract claims, description, examples, measured properties
- Evaluate evidence coverage (`high` / `medium` / `low` / `metadata_only`)
- Export JSON/CSV and `fulltext_evidence_report.md`
- No OpenAlex, no Deep Dive analysis in this step

### Step 5: Claim Element Extraction

- Input: `top5_fulltext_records.json` from Phase 4
- Rule-based decomposition of claims into technical elements (material, process, structure, property, etc.)
- Map support from description, examples, and measured properties
- Generate OpenAlex paper query candidates (no search in this step)
- Export `claim_elements.json/csv`, `paper_query_candidates.csv`, `claim_element_report.md`
- LLM-based extraction remains optional for future extension

### Step 6: OpenAlex Paper Evidence Search

- Input: `paper_query_candidates.csv` and `claim_elements.csv` from Phase 5
- Plan-only by default; explicit `--execute` for OpenAlex API calls
- Cache-first JSON storage per query
- Normalize works to `PaperRecord` with `display_url` and source metadata
- Evaluate paper source quality with `SourceQualityAgent` v1
- Map papers to claim elements as evidence relation candidates
- Export `paper_evidence_links.csv` and `paper_evidence_report.md`
- No web signal search or final synthesis report in this step

### Step 7: Patent Claim × Paper Evidence Map

- Input: Phase 5 `claim_elements.csv` and Phase 6 paper evidence outputs
- Integrate claim elements with paper evidence links and source quality
- Assign evidence relation, confidence, caveat, and human review recommendations
- Build patent-level evidence maps and evidence gap analysis
- Export `claim_paper_evidence_items.csv` and `claim_paper_evidence_map_report.md`
- No web signal search or final synthesis report in this step

### Step 8: Technical View Agent

- Input: Phase 7 patent evidence maps, evidence items, and evidence gaps
- Rule-based technical assessment for engineers (no Business View yet)
- Score evidence strength, description/example support, paper support, measurement risk, implementation risk
- Output patent technical summaries, assessment items, and recommended reader actions
- Export `technical_assessments.json` and `technical_view_report.md`
- No web signal mapping or final synthesis report in this step

### Step 9: Web / Company Signal Mapping

- Input: manual web signal CSV/JSON/YAML and patents CSV
- Normalize company names and evaluate web source quality
- Map signals to patents and technology clusters
- Export `web_signal_patent_links.csv` and `web_signal_report.md`
- No automatic Tavily/web search or Business View Agent in this step

### Step 10: Business View Agent

- Input: technical assessments, patent technical summary, web signal patent links
- Rule-based business assessment for SMEs (commercialization signals, competitive watch, SME opportunity, design-around candidates)
- Export `business_assessments.json`, `patent_business_summary.csv`, and `business_view_report.md`
- No Synthesis Report, automatic Tavily/web search, or monthly update automation in this step

### Step 11: Synthesis Report

- Input: cluster summary, top20/top5 patents, technical and business assessments
- Integrate patent ranking, claim/paper evidence, technical view, and business view
- Export `carbon_fiber_evidence_map_v1.md`, `key_findings.csv`, `priority_patents.csv`, `sme_action_plan.csv`
- No monthly/biweekly automation, email delivery, or cloud deployment in this step

### Step 12: Periodic Update Automation (future)

- Monthly / biweekly evidence map refresh
- Optional email delivery and cloud scheduling

### Step 12 (v7 Phase 12): One Command Pipeline Runner

- Goal: run Phase 1–11 in one command for reproducible case studies
- Save `run_manifest.json`, `run_summary.md`, and `artifact_index.md` per run
- Safe-by-default: external API stages execute only with explicit flags

### Step 13 (v7 Phase 13): Ranking Quality and Easy Japanese UI

- Goal: fix Top20/Top5 noise issues seen in real-data runs; add SME-friendly Japanese UI
- Stronger noise filter (display, sensor membrane, 3D printing carbon/graphite, battery, graphene/CNT, activated carbon, unknown assignee)
- Boost core carbon-fiber manufacturing / surface / bundle / property terms in ranking
- Top5 fulltext selector: US-first, manual route for JP/EP/WO/CN/KR, `why_selected_japanese` and quality flags
- Streamlit Easy Japanese View (7 steps) alongside Expert Pipeline View
- No new external APIs; no additional BigQuery/OpenAlex/fulltext execution logic

### Step 13.1 (v7 Phase 13.1): Non-US Strategic Watch Candidates

- Keep Top5 fulltext US-prioritized for BigQuery retrieval feasibility
- Add Strategic Watch Candidates for CN/EP/JP/WO/KR (Zhongfu Shenying, etc.)
- Separate `strategic_score` from `fulltext_route_score` in ranking
- Export `strategic_watch_candidates.csv`, `country_watch_summary.csv`, `company_watch_summary.csv`
- Easy Japanese UI shows US Top5 and Strategic Watch as distinct sections

### Step 14 (v7 Phase 14): Controlled Full Text Run

- US Top5 only for BigQuery fulltext retrieval (`--execute-fulltext` explicit)
- Default dry-run: plan + cost estimate, no BigQuery execution
- Strategic watch CN/EP/JP → manual fulltext package (not excluded)
- Outputs: `fulltext_plan.json`, `manual_fulltext_checklist.md`, `strategic_watch_manual_fulltext_required.csv`
- No automatic PDF download, OCR, or web search in this step

### Step 15 (v7 Phase 15): Evidence Validation Pipeline

- Assess fulltext readiness (`ready` / `limited` / `dry_run_only` / `manual_required`)
- Claim element extraction only for US records with fetched claims/description
- OpenAlex default plan-only; explicit `--execute-openalex` for limited run
- Build claim×paper evidence links and `evidence_validation_report.md`
- CN/EP/JP manual watch candidates retained (not excluded)
- Does not prove patent claims from papers; expert review required

### Step 16 (v7 Phase 16): Controlled Full Text Execute Trial

- Execute US Top5 fulltext for **1件 or specified publication only**
- Requires `--confirm-fulltext-execute` (no silent execute)
- Preview dry-run cost per candidate before execute
- `skipped_not_selected` for non-selected US targets
- CN/EP/JP manual watch unchanged
- Outputs: `fulltext_execute_preview.json`, `fulltext_execute_results.csv`
- Retrieved/cache_hit records flow into Evidence Validation claim extraction

### Step 16.1 (v7 Phase 16.1): Fulltext Scope + GB/USD Cost Guard

- Split fulltext scope: `claims_only` (default), `description_only`, `claims_and_description`
- Dual cost guard: `maximum_fulltext_gb` + `maximum_fulltext_usd`
- GB over limit but USD OK → `cost_guard_requires_expensive_confirmation` + `recommended_expensive_command`
- `--allow-expensive-fulltext` required for expensive execute
- Per-candidate scope dry-run estimates in `fulltext_execute_preview.json`
- Execute quality gate for carbon-fiber relevance (low-priority US noise deprioritized)
- `claims_only` → limited claim extraction without description
- CN/EP/JP manual watch unchanged; do not auto-execute all Top5 or `claims_and_description` unconditionally

### Step 16.2 (v7 Phase 16.2): Internal Cost Policy + Adaptive Ledger

- Usage-based monetization prep: internal cost policies per execution type (`watch_run`, `claims_check`, …)
- **No user-facing prices** — UI/reports show acquisition policy, scope, stop reasons only
- Safety margin 1.3; `raw_cost_cap_usd` as internal stop line; `buffered_cost_cap_usd` for pricing design
- Actual cost ledger from BigQuery job bytes billed (internal estimate, not final invoice)
- Adaptive retrieval: skip candidates when next estimate exceeds remaining budget (`skipped_budget_guard`)
- Weekly Digest Preview generated (no email sending yet)
- CN/EP/JP remain Strategic Watch / manual route

### Step 17 (v7 Phase 17): Login + Tabbed Japanese UI

- Local email login (no password, no OAuth, no production auth)
- `outputs/user_store/users.json` + per-user watch profiles
- Tabbed Easy Japanese View (app2.py-inspired cards)
- Weekly email ON/OFF saved only (no SMTP/Scheduler)
- User `last_run_id` preference for pipeline results
- BigQuery/OpenAlex not auto-triggered from UI
