# PatentScout AI v7 — Carbon Fiber Evidence Map

Patent Evidence Intelligence scaffold for carbon-fiber technology cartography.

v7 is a fresh project. It does not inherit v6's weekly-watch baseline as a bulk copy.

## Scope

- Carbon Fiber Evidence Map
- Patent Evidence Intelligence
- Tech cartography under `src/tech_cartography/`

## Layout

- `app.py` — application entry point
- `configs/` — runtime and case-study configuration
- `case_studies/carbon_fiber/` — carbon fiber reference cases
- `src/tech_cartography/` — core package
- `scripts/` — operational scripts
- `tests/` — test suite
- `data/reference/` — curated reference inputs
- `data/runtime/` — generated runtime artifacts (gitignored)
- `outputs/` — generated reports and exports (gitignored)

## Setup

Use the `2026hack` conda environment:

```bash
conda activate 2026hack
cd PatentScout_AI_v7
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

## Test

```bash
python -m pytest -q
```

## v7 Phase 1: Search Strategy Builder

Phase 1 focuses on building search strategy before any BigQuery execution.

- User input or `configs/carbon_fiber_demo_profile.yaml` becomes a `SearchProfile`
- Optional seed patents are analyzed by `SeedPatentAnalyzer`
- `SearchStrategyBuilder` generates intent-specific query plans:
  - `core_manufacturing`
  - `surface_interface`
  - `bundle_prepreg`
  - `application`
  - `company_watch`
- Recommended first plan: `core_manufacturing`
- BigQuery execution is deferred to the next phase

### Phase 1 deliverables

- Domain models: `SearchProfile`, `PatentRecord`, `QueryPlan`
- Strategy modules under `src/tech_cartography/strategy/`
- Demo config under `configs/`
- Minimal Streamlit UI via `streamlit run app.py`

See also: `docs/carbon_fiber_evidence_map_plan.md`

## v7 Phase 2: BigQuery Light Multi-Query Retrieval

Phase 2 executes lightweight BigQuery retrieval for each `QueryPlan` from Phase 1.

- Metadata only: title, abstract, assignee, publication metadata, CPC/IPC
- No claims, description, or full text
- Dry-run by default with estimated GB / USD
- `--execute` required for actual BigQuery execution
- `maximum_bytes_billed` cap enforced per query
- Results saved to `outputs/bigquery_light_retrieval/{timestamp}/`
- Raw and deduplicated CSV plus `retrieval_summary.json`
- Each record includes `search_intents`, `query_plan_ids`, `matched_terms`, `source_type`, `evidence_level`

### Important note on LIMIT

`LIMIT` alone does not reduce bytes scanned. Always filter with `WHERE` on
`publication_date`, `country_code`, include terms, and exclude terms.

### CLI examples

```bash
python scripts/run_bigquery_light_search.py --max-results-total 2000 --max-results-per-intent 500 --maximum-gb 300

python scripts/run_bigquery_light_search.py --execute --max-results-total 2000 --max-results-per-intent 500 --maximum-gb 300
```

Default mode is dry-run. Pass `--execute` only when you intend to bill BigQuery.

## v7 Phase 3: Technology Clustering & Patent Ranking

Phase 3 consumes Phase 2 deduplicated CSV and produces:

- `classified_patents.csv`
- `ranked_patents.csv`
- `top20_patents.csv`
- `top5_fulltext_candidates.csv`
- `cluster_summary.json`
- `carbon_fiber_evidence_map_report.md`

### CLI example

```bash
python scripts/build_carbon_fiber_case_study.py \
  --input-csv outputs/bigquery_light_retrieval/latest/bigquery_light_results_dedup.csv \
  --top-n 20 \
  --fulltext-top-n 5
```

Rule-based classification is the default. LLM-based clustering is reserved for future optional extension.

## v7 Phase 4: Top5 Full Text Evidence Collection

Phase 4 collects full text evidence for Top5 candidates from Phase 3.

- US publications: BigQuery full text route (`claims_localized`, `description_localized`)
- Non-US publications: `manual_fulltext_required` route
- Dry-run by default; `--execute` required for BigQuery billing
- `maximum_bytes_billed`, cache, and cost guard enforced
- Evidence coverage and `evidence_level` assigned per record
- Manual upload supported via TXT / MD / CSV / XLSX loader

### CLI examples

```bash
python scripts/run_top5_fulltext_collection.py \
  --input-csv outputs/carbon_fiber_case_study/latest/top5_fulltext_candidates.csv \
  --maximum-gb 50

python scripts/run_top5_fulltext_collection.py \
  --input-csv outputs/carbon_fiber_case_study/latest/top5_fulltext_candidates.csv \
  --maximum-gb 50 \
  --execute
```

Outputs are saved under `outputs/top5_fulltext_collection/{timestamp}/`.
