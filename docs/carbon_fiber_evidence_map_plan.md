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

### Step 5: Paper/Web Evidence Mapping

- Map patent clusters to papers and web signals
- Produce Carbon Fiber Evidence Map outputs for review
