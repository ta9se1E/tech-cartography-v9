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

## v7 Phase 5: Claim Element Extraction

Phase 5 consumes Phase 4 `top5_fulltext_records.json` and decomposes patent claims into technical elements for the next OpenAlex paper evidence search phase.

- Rule-based extraction from claims, description, examples, and measured properties
- Element types: material, process, structure, property, numerical_condition, application, and more
- Support mapping: `supported_by_description`, `supported_by_examples`, `supported_by_measured_properties`, `claim_only`, `metadata_only`
- Paper query candidates generated (search not executed in this phase)
- Each element includes `source_section` and `evidence_snippet`
- Records without claims use `metadata_only` or limited extraction

### CLI example

```bash
python scripts/run_claim_element_extraction.py \
  --input-json outputs/top5_fulltext_collection/latest/top5_fulltext_records.json
```

Outputs are saved under `outputs/claim_element_extraction/{timestamp}/`:

- `claim_elements.json` / `claim_elements.csv`
- `record_claim_element_summary.json`
- `paper_query_candidates.csv`
- `claim_element_report.md`

## v7 Phase 6: OpenAlex Paper Evidence Search

Phase 6 consumes Phase 5 `paper_query_candidates.csv` and optionally `claim_elements.csv` to retrieve related papers from OpenAlex and map them to claim elements.

- Default mode is plan-only (`execute=False`); pass `--execute` to call OpenAlex API
- Cache-first under `data/runtime/openalex_cache/`
- `PaperRecord` normalization with `display_url`, DOI, and source metadata
- `SourceQualityAgent` v1 evaluates reference usability (not technical truth)
- `PaperEvidenceMapper` links papers to claim elements as supporting/background/weak/unrelated candidates
- No web signal search, business agents, or final synthesis report in this phase

### CLI examples

```bash
python scripts/run_openalex_evidence.py \
  --paper-query-csv outputs/claim_element_extraction/latest/paper_query_candidates.csv \
  --claim-elements-csv outputs/claim_element_extraction/latest/claim_elements.csv \
  --max-queries 20 \
  --max-results-per-query 10

python scripts/run_openalex_evidence.py \
  --paper-query-csv outputs/claim_element_extraction/latest/paper_query_candidates.csv \
  --claim-elements-csv outputs/claim_element_extraction/latest/claim_elements.csv \
  --max-queries 20 \
  --max-results-per-query 10 \
  --execute
```

Outputs are saved under `outputs/openalex_paper_evidence/{timestamp}/`:

- `openalex_query_plan.json`
- `paper_records_raw.json` / `paper_records.csv` / `paper_records_dedup.csv`
- `source_quality_results.csv`
- `paper_evidence_links.csv`
- `paper_evidence_by_patent.json`
- `paper_evidence_report.md`

## v7 Phase 7: Patent Claim × Paper Evidence Map

Phase 7 integrates Phase 5 claim elements and Phase 6 OpenAlex paper evidence into a patent-level evidence candidate map.

- Combines `claim_elements.csv`, `paper_evidence_links.csv`, `paper_records_dedup.csv`, and `source_quality_results.csv`
- Builds `ClaimPaperEvidenceItem` rows with `evidence_relation`, `evidence_confidence`, `caveat`, and `recommended_human_check`
- Creates `PatentEvidenceMap` per publication with coverage and gap summaries
- Detects evidence gaps (`no_paper_found`, `weak_only`, `background_only`, etc.)
- Papers are evidence candidates only — not proof of patent claims
- No web signal search, business agents, or final synthesis report in this phase

### CLI example

```bash
python scripts/build_claim_paper_evidence_map.py \
  --claim-elements-csv outputs/claim_element_extraction/latest/claim_elements.csv \
  --paper-links-csv outputs/openalex_paper_evidence/latest/paper_evidence_links.csv \
  --paper-records-csv outputs/openalex_paper_evidence/latest/paper_records_dedup.csv \
  --source-quality-csv outputs/openalex_paper_evidence/latest/source_quality_results.csv \
  --top-n 30
```

Outputs are saved under `outputs/claim_paper_evidence_map/{timestamp}/`:

- `claim_paper_evidence_items.csv`
- `patent_evidence_maps.json`
- `evidence_by_element_type.csv`
- `evidence_gaps.csv`
- `top_evidence_items.csv`
- `claim_paper_evidence_map_summary.json`
- `claim_paper_evidence_map_report.md`

## v7 Phase 8: Technical View Agent

Phase 8 consumes Phase 7 claim-paper evidence map outputs and produces rule-based technical assessments for engineers.

- Input: `patent_evidence_maps.json`, `claim_paper_evidence_items.csv`, `evidence_gaps.csv`
- Optional: `claim_elements.csv`, `top5_fulltext_records.json`
- Patent-level technical score, confidence, summary, risks, and recommended checks
- Assessment items for evidence strength, claim scope risk, implementation risk, measurement risk, and human review
- Uses cautious wording: evidence candidates, not proof
- No Business View Agent, web signal mapping, or final synthesis report in this phase

### CLI example

```bash
python scripts/run_technical_view_agent.py \
  --patent-evidence-maps-json outputs/claim_paper_evidence_map/latest/patent_evidence_maps.json \
  --evidence-items-csv outputs/claim_paper_evidence_map/latest/claim_paper_evidence_items.csv \
  --evidence-gaps-csv outputs/claim_paper_evidence_map/latest/evidence_gaps.csv
```

Outputs are saved under `outputs/technical_view_assessment/{timestamp}/`:

- `technical_assessments.json`
- `technical_assessment_items.csv`
- `patent_technical_summary.csv`
- `common_technical_risks.json`
- `technical_view_report.md`

## v7 Phase 9: Web / Company Signal Mapping

Phase 9 maps manually curated web / company signals to patents and technology clusters.

- Input: web signal CSV/JSON/YAML and patents CSV (`top20_patents.csv` or `ranked_patents.csv`)
- Company name normalization (TORAY / 東レ / TORAY INDUSTRIES, etc.)
- Web signal source quality evaluation (official / IR / press release / industry news)
- Patent linkage with `business_signal_candidate`, `technology_background_signal`, `weak_signal`, `unrelated`
- Default is manual file input; Tavily/automatic web search is future extension only
- No Business View Agent or final synthesis report in this phase

### CLI example

```bash
python scripts/run_web_signal_mapping.py \
  --web-signal-file case_studies/carbon_fiber/web_signals/carbon_fiber_web_signals_template.csv \
  --patents-csv outputs/carbon_fiber_case_study/latest/top20_patents.csv
```

Outputs are saved under `outputs/web_signal_mapping/{timestamp}/`:

- `normalized_web_signals.csv`
- `web_signal_quality_results.csv`
- `web_signal_patent_links.csv`
- `web_signals_by_patent.json`
- `web_signals_by_company.csv`
- `web_signals_by_cluster.csv`
- `web_signal_report.md`

## v7 Phase 10: Business View Agent

Phase 10 integrates technical assessment (Phase 8) and web/company signal mapping (Phase 9) into preliminary business intelligence for SMEs.

- Input: `technical_assessments.json`, `patent_technical_summary.csv`, `web_signal_patent_links.csv`
- Optional: `ranked_patents.csv`, `patent_evidence_maps.json`
- Rule-based business assessment (no automatic web search, no synthesis report yet)
- Outputs commercialization signal candidates, competitive watch points, SME opportunity candidates, design-around hints, and recommended reader actions
- Web signals are treated as business context candidates, not proof of commercialization

### CLI example

```bash
python scripts/run_business_view_agent.py \
  --technical-assessments-json outputs/technical_view_assessment/latest/technical_assessments.json \
  --patent-technical-summary-csv outputs/technical_view_assessment/latest/patent_technical_summary.csv \
  --web-signal-links-csv outputs/web_signal_mapping/latest/web_signal_patent_links.csv
```

Outputs are saved under `outputs/business_view_assessment/{timestamp}/`:

- `business_assessments.json`
- `business_assessment_items.csv`
- `patent_business_summary.csv`
- `sme_opportunity_candidates.csv`
- `design_around_candidates.csv`
- `common_business_risks.json`
- `business_view_report.md`

## v7 Phase 11: Synthesis Report

Phase 11 integrates Phase 1–10 outputs into a single Carbon Fiber Evidence Map report for SMEs.

- Input: cluster summary, top20/top5 patents, technical and business assessments
- Optional: claim/paper evidence map summary, evidence gaps, web signals by company/cluster
- Rule-based synthesis (no automatic updates, email, or cloud deployment)
- Outputs executive summary, key findings, priority patents, SME action plan, and caveats

### CLI example

```bash
python scripts/build_synthesis_report.py \
  --cluster-summary-json outputs/carbon_fiber_case_study/latest/cluster_summary.json \
  --top20-csv outputs/carbon_fiber_case_study/latest/top20_patents.csv \
  --top5-csv outputs/carbon_fiber_case_study/latest/top5_fulltext_candidates.csv \
  --technical-assessments-json outputs/technical_view_assessment/latest/technical_assessments.json \
  --patent-technical-summary-csv outputs/technical_view_assessment/latest/patent_technical_summary.csv \
  --business-assessments-json outputs/business_view_assessment/latest/business_assessments.json \
  --patent-business-summary-csv outputs/business_view_assessment/latest/patent_business_summary.csv \
  --theme "PAN系炭素繊維の中温域炭化条件最適化"
```

Outputs are saved under `outputs/synthesis_report/{timestamp}/`:

- `synthesis_report.json`
- `key_findings.csv`
- `priority_patents.csv`
- `sme_action_plan.csv`
- `next_update_recommendations.json`
- `carbon_fiber_evidence_map_v1.md`

## v7 Phase 12: One Command Pipeline Runner

Phase 12 connects Phase 1–11 modules into a one-command pipeline runner for reproducible Carbon Fiber case studies.

- Safe-by-default: external API stages do not execute unless explicitly enabled
  - BigQuery: `--execute-bigquery` or reuse existing CSV
  - Full text: `--execute-fulltext` or reuse cached/manual artifacts
  - OpenAlex: `--execute-openalex` (or cache)
- Run manifest + artifact index are saved per run (no symlinks)

### CLI example

```bash
python scripts/run_carbon_fiber_evidence_map.py --config configs/carbon_fiber_pipeline.yaml
```

Outputs are saved under `outputs/pipeline_runs/{run_id}/`:

- `run_manifest.json`
- `run_summary.md`
- `artifact_index.json`
- `artifact_index.md`
- stage outputs under `stages/*/`

## v7 Phase 13: Ranking Quality and Easy Japanese UI

Phase 13 improves Top20/Top5 candidate quality and adds a non-expert Japanese UI inspired by v6 `app2.py`.

- Stronger noise filtering (display/sensor/3D printing/battery/graphene/CNT/activated carbon, unknown assignee penalty)
- Core carbon-fiber manufacturing term boosting (PAN, carbonization, surface treatment, prepreg, tensile strength, etc.)
- Top5 fulltext selection prefers US + low-noise + core clusters (CN/EP/JP/WO → manual route)
- Japanese labels, card UI, and 7-step Easy Japanese View in Streamlit

### UI

```bash
streamlit run app.py
```

Sidebar: **Expert Pipeline View** or **Easy Japanese View**

### CLI re-run example (clustering only, existing light CSV)

```bash
python scripts/run_carbon_fiber_evidence_map.py \
  --config configs/carbon_fiber_pipeline.yaml \
  --use-existing-light-csv outputs/pipeline_runs/<run_id>/stages/bigquery_light_retrieval/<ts>/bigquery_light_results_dedup.csv \
  --start-stage technology_clustering_ranking \
  --stop-stage technology_clustering_ranking
```

New/updated modules:

- `src/tech_cartography/curation/noise_filter.py`
- `src/tech_cartography/curation/patent_ranker.py`
- `src/tech_cartography/curation/top_candidate_selector.py`
- `src/tech_cartography/ui/japanese_labels.py`
- `src/tech_cartography/ui/easy_japanese_ui.py`
- `src/tech_cartography/ui/v7_easy_app.py`

## v7 Phase 13.1: Non-US Strategic Watch Candidates

Phase 13.1 separates **Top5 Fulltext Candidates** (US-first for BigQuery retrieval) from **Strategic Watch Candidates** (CN/EP/JP/WO/KR and global competition monitoring).

- Top5 remains US-prioritized for fulltext retrieval — not a global importance ranking
- Strategic Watch keeps Zhongfu Shenying and other major CN/EP/JP patents visible
- New outputs: `strategic_watch_candidates.csv`, `country_watch_summary.csv`, `company_watch_summary.csv`
- `app.py` adds `src/` to `sys.path` so `streamlit run app.py` works without editable install

### Run UI

```bash
streamlit run app.py
```

Sidebar: **Easy Japanese View** shows US Top5 and Strategic Watch side by side.

## v7 Phase 14: Controlled Full Text Run

Phase 14 runs a **controlled** full text collection for US Top5 candidates only, while preserving CN/EP/JP strategic watch candidates in a manual fulltext package.

- Default: **dry-run / plan-only** (`execute_fulltext=False`)
- `--execute-fulltext` runs BigQuery for US targets only (cache-first, `maximum_bytes_billed` guard)
- Non-US strategic watch → `strategic_watch_manual_fulltext_required.csv` + `manual_fulltext_checklist.md`
- Claims not fetched does **not** mean low strategic value

### CLI example (dry-run through fulltext stage)

```bash
python scripts/run_carbon_fiber_evidence_map.py \
  --config configs/carbon_fiber_pipeline.yaml \
  --use-existing-light-csv outputs/pipeline_runs/<run_id>/stages/bigquery_light_retrieval/<ts>/bigquery_light_results_dedup.csv \
  --start-stage technology_clustering_ranking \
  --stop-stage top5_fulltext_collection
```

### Execute fulltext (US only)

```bash
python scripts/run_carbon_fiber_evidence_map.py \
  --config configs/carbon_fiber_pipeline.yaml \
  --use-existing-light-csv <light_csv> \
  --start-stage technology_clustering_ranking \
  --stop-stage top5_fulltext_collection \
  --execute-fulltext
```

Outputs under `stages/top5_fulltext_collection/`:

- `fulltext_plan.json`
- `top5_fulltext_records.json` / `.csv`
- `manual_fulltext_required.csv`
- `strategic_watch_manual_fulltext_required.csv`
- `manual_fulltext_checklist.md`
- `fulltext_evidence_report.md`

## v7 Phase 15: Evidence Validation Pipeline

Phase 15 validates fulltext readiness and runs a **safe** Claim Element × OpenAlex evidence check from Phase 14 outputs.

- `evidence_validation` stage sits after `top5_fulltext_collection` (existing claim/openalex stages remain for compatibility)
- Default: **OpenAlex plan-only** (`execute_openalex=False`); `--execute-openalex` for limited execution (cache-first)
- US records with fetched claims/description → claim element extraction; dry-run only → `limited_no_fulltext` (not a failure)
- CN/EP/JP manual watch candidates preserved in `manual_fulltext_watch.csv`
- Paper evidence is **Evidence Candidate**, not proof of patent claims

### Standalone CLI (plan-only)

```bash
python scripts/run_evidence_validation.py \
  --fulltext-records-json outputs/pipeline_runs/<run_id>/stages/top5_fulltext_collection/top5_fulltext_records.json \
  --manual-candidates-csv outputs/pipeline_runs/<run_id>/stages/top5_fulltext_collection/strategic_watch_manual_fulltext_required.csv
```

### Pipeline through evidence_validation

```bash
python scripts/run_carbon_fiber_evidence_map.py \
  --config configs/carbon_fiber_pipeline.yaml \
  --use-existing-light-csv outputs/pipeline_runs/<run_id>/stages/bigquery_light_retrieval/<ts>/bigquery_light_results_dedup.csv \
  --start-stage technology_clustering_ranking \
  --stop-stage evidence_validation
```

Outputs under `stages/evidence_validation/`:

- `fulltext_readiness.json`
- `ready_for_claim_extraction.csv`
- `manual_fulltext_watch.csv`
- `claim_elements.csv`
- `paper_query_candidates.csv`
- `openalex_query_plan.json`
- `paper_evidence_links.csv`
- `claim_paper_evidence_items.csv`
- `evidence_validation_summary.json`
- `evidence_validation_report.md`

## v7 Phase 16: Controlled Full Text Execute Trial

Phase 16 adds **safe, limited** BigQuery fulltext execution for US Top5 only (1件または指定件数).

- Default: still **no execute** — requires `--execute-fulltext` + `--confirm-fulltext-execute`
- `--fulltext-execute-limit 1` — Top1 only (default limit=1)
- `--fulltext-publication-number US-...` — single publication execute
- Non-selected US targets → `skipped_not_selected`
- CN/EP/JP remain manual strategic watch (not excluded)
- Outputs: `fulltext_execute_preview.json`, `fulltext_execute_results.csv`

### Dry-run through evidence_validation (no BigQuery execute)

```bash
python scripts/run_carbon_fiber_evidence_map.py \
  --config configs/carbon_fiber_pipeline.yaml \
  --use-existing-light-csv outputs/pipeline_runs/<run_id>/stages/bigquery_light_retrieval/<ts>/bigquery_light_results_dedup.csv \
  --start-stage technology_clustering_ranking \
  --stop-stage evidence_validation
```

### Recommended: Top1 execute trial (when ready to run BigQuery)

```bash
python scripts/run_carbon_fiber_evidence_map.py \
  --config configs/carbon_fiber_pipeline.yaml \
  --use-existing-light-csv outputs/pipeline_runs/<run_id>/stages/bigquery_light_retrieval/<ts>/bigquery_light_results_dedup.csv \
  --start-stage technology_clustering_ranking \
  --stop-stage evidence_validation \
  --execute-fulltext \
  --fulltext-execute-limit 1 \
  --confirm-fulltext-execute
```

### Standalone Top1 execute

```bash
python scripts/run_top5_fulltext_collection.py \
  --input-csv outputs/pipeline_runs/<run_id>/stages/technology_clustering_ranking/top5_fulltext_candidates.csv \
  --strategic-watch-csv outputs/pipeline_runs/<run_id>/stages/technology_clustering_ranking/strategic_watch_candidates.csv \
  --maximum-gb 50 \
  --execute \
  --execute-limit 1 \
  --confirm-fulltext-execute
```
