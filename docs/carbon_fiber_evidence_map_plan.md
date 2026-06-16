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

### Step 3: AI Technology Clustering

- Cluster retrieved patents into technology branches for the evidence map
- Label clusters with materials, processes, properties, and applications

### Step 4: Top5 Full Text Evidence Collection

- Select top clusters and collect full-text evidence for representative patents
- Score evidence readiness for downstream mapping

### Step 5: Paper/Web Evidence Mapping

- Map patent clusters to papers and web signals
- Produce Carbon Fiber Evidence Map outputs for review
