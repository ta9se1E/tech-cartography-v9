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
