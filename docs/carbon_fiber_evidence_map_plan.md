# Carbon Fiber Evidence Map Plan

## Roadmap

### Step 1: Search Strategy Builder

- Build `SearchProfile` from user input or demo YAML
- Analyze optional seed patents with `SeedPatentAnalyzer`
- Generate intent-specific `QueryPlan` objects for carbon fiber evidence mapping
- Recommend `core_manufacturing` as the first plan
- No BigQuery execution in this step

### Step 2: BigQuery Light Multi-Query Retrieval

- Execute each query plan in lightweight dry-run / capped retrieval mode
- Merge results into a retrieval corpus with source audit metadata

### Step 3: AI Technology Clustering

- Cluster retrieved patents into technology branches for the evidence map
- Label clusters with materials, processes, properties, and applications

### Step 4: Top5 Full Text Evidence Collection

- Select top clusters and collect full-text evidence for representative patents
- Score evidence readiness for downstream mapping

### Step 5: Paper/Web Evidence Mapping

- Map patent clusters to papers and web signals
- Produce Carbon Fiber Evidence Map outputs for review
