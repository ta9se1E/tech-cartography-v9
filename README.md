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

## v7 Phase 16.1: Fulltext Scope + GB/USD Cost Guard

Phase 16.1 refines controlled fulltext execution with **scoped retrieval** and **dual cost guards** (GB + USD).

- `fulltext_scope`: `claims_only` (default) | `description_only` | `claims_and_description`
- `maximum_fulltext_usd` (default 10.0) — USD budget guard separate from GB limit
- `--allow-expensive-fulltext` — required when GB exceeds limit but USD is within budget
- Per-candidate × per-scope dry-run estimates saved in `fulltext_execute_preview.json` (`scope_estimates`)
- Execute quality gate filters low-priority US noise (display/vessel assessment, etc.)
- `claims_only` success → limited claim extraction / Evidence Validation `partial_success`
- CN/EP/JP remain manual route (not excluded)

### claims_only dry-run + execute (when GB high but USD OK)

```bash
python scripts/run_carbon_fiber_evidence_map.py \
  --config configs/carbon_fiber_pipeline.yaml \
  --use-existing-light-csv outputs/pipeline_runs/<run_id>/stages/bigquery_light_retrieval/<ts>/bigquery_light_results_dedup.csv \
  --start-stage technology_clustering_ranking \
  --stop-stage evidence_validation \
  --execute-fulltext \
  --fulltext-publication-number US-12565719-B2 \
  --fulltext-scope claims_only \
  --confirm-fulltext-execute
```

If dry-run shows GB over limit but USD within budget, add:

```bash
  --allow-expensive-fulltext \
  --maximum-fulltext-usd 10
```

## v7 Phase 16.2: Internal Cost Policy + Adaptive Ledger

Phase 16.2 adds **internal acquisition policies**, **actual cost ledger**, and **adaptive retrieval control** for future usage-based monetization — **without showing prices to users**.

- Internal policies: `watch_run` | `claims_check` | `full_deep_dive` | `technical_review` | `deep_research` (`configs/internal_cost_policy.yaml`)
- Safety margin 1.3, target cost ratio 50% (internal design only)
- BigQuery dry-run estimates + job actual bytes billed → `outputs/cost_ledger/cost_ledger.jsonl` + per-run `cost_ledger.csv`
- Adaptive controller stops when cumulative actual cost nears `raw_cost_cap_usd`
- User-facing outputs (no USD): `acquisition_policy_summary.md`, `weekly_digest_preview.md`
- CLI: `--internal-cost-policy watch_run` (etc.), `--disable-cost-ledger`

### Watch Run (metadata monitoring only)

```bash
python scripts/run_carbon_fiber_evidence_map.py \
  --config configs/carbon_fiber_pipeline.yaml \
  --use-existing-light-csv outputs/pipeline_runs/<run_id>/stages/bigquery_light_retrieval/<ts>/bigquery_light_results_dedup.csv \
  --start-stage technology_clustering_ranking \
  --stop-stage evidence_validation \
  --internal-cost-policy watch_run
```

### Claims Check (US Top1 claims_only)

```bash
python scripts/run_carbon_fiber_evidence_map.py \
  --config configs/carbon_fiber_pipeline.yaml \
  --use-existing-light-csv outputs/pipeline_runs/<run_id>/stages/bigquery_light_retrieval/<ts>/bigquery_light_results_dedup.csv \
  --start-stage technology_clustering_ranking \
  --stop-stage evidence_validation \
  --internal-cost-policy claims_check \
  --execute-fulltext \
  --fulltext-publication-number US-12565719-B2 \
  --fulltext-scope claims_only \
  --confirm-fulltext-execute
```

## v7 Phase 18B: Manual Fulltext Input Route

When BigQuery public data has no claims/description (e.g. `US-12565719-B2`), paste text from Google Patents into local files and import via CLI. Patent body text is **not** committed to the repo — keep it under `inputs/manual/` locally.

Example local file names (user-provided content only):

- `inputs/manual/US-12565719-B2_claims.txt`
- `inputs/manual/US-12565719-B2_description.txt`

Import:

```bash
python scripts/import_manual_fulltext.py \
  --publication-number US-12565719-B2 \
  --source-url https://patents.google.com/patent/US12565719B2 \
  --claims-file inputs/manual/US-12565719-B2_claims.txt \
  --input-route manual_google_patents \
  --entered-by local_user
```

Saved to `outputs/manual_fulltext_inputs/US-12565719-B2.json`. The pipeline picks this up when BigQuery fulltext is `not_found` / `manual_route_recommended` (`enable_manual_fulltext_fallback: true` by default).

## v7 Phase 18C: Claims-based Paper Query Plan

Generate OpenAlex search query candidates from manual claims (plan_only; API execution optional).

```bash
python scripts/build_claims_paper_query_plan.py \
  --manual-input outputs/manual_fulltext_inputs/US-12565719-B2.json

python scripts/build_claims_paper_query_plan.py \
  --run-dir outputs/pipeline_runs/<run_id> \
  --publication-number US-12565719-B2
```

Outputs: `paper_query_candidates_from_claims.csv/json`, `claims_paper_query_plan.md`, `paper_query_quality_report.md`. Confidence is `medium` or `low` for claims-only input; target 5–10 query candidates with quality gate (`plan_ready_for_openalex`). Papers are supporting evidence candidates, not proof.

```bash
python scripts/build_claims_paper_query_plan.py \
  --manual-input outputs/manual_fulltext_inputs/US-12565719-B2.json \
  --min-queries 5 --max-queries 10 --quality-report
```

## v7 Phase 17: Login + Tabbed Japanese UI

Phase 17 adds **app2.py-style** Easy Japanese UI with local email login and tab navigation.

- Login with email (no password; local dev only)
- User profile + Watch Profile stored in `outputs/user_store/`
- Tabbed UI: はじめる / 特許候補 / 全文確認 / 技術の裏取り / 企業・市場シグナル / レポート / 設定
- Weekly email settings (save only; no sending yet)
- `user.last_run_id` linked when loading pipeline results

### Start the app

```bash
streamlit run app.py
```

- First screen: email login
- After login: tabbed Easy Japanese View
- CLI / pipeline unchanged (`scripts/run_carbon_fiber_evidence_map.py` etc.)

### Phase 24.4A — 別テーマ検証 UI

Streamlit の **別テーマ検証** トップレベルタブで操作します（レポートタブ内ではありません）。

- 独自テーマのキーワード入力 → 検索計画 dry-run（外部 API 未実行）
- 既存 `outputs/` の Stage 検証（Evidence Map / Link Candidate / Strategic Watch / Digest）
- 明示同意後のみ特許候補の BigQuery 検索（未設定時は `external_search_not_configured`）
- Manual Claims テンプレート生成と検証レポート保存

詳細: `docs/phase24_theme_validation_ui.md`

## CI/CD and Deployment Safety

Study Demo uses GitHub Actions for **CI** and **approved Continuous Delivery**:

- **CI** (`.github/workflows/ci.yml`): runs on push/PR to `v9-study-demo` via `scripts/run_v9_ci_checks.sh`
  - compileall, pytest (1108+), readiness, build-context safety, final acceptance plan checks
  - no Cloud auth, no secrets, no external APIs
- **CD** (`.github/workflows/deploy-study-demo.yml`): `workflow_dispatch` only
  - GitHub Environment `study-demo` approval required
  - Workload Identity Federation (keyless; no Service Account JSON)
  - deploys **validated tag only** (`v9-study-demo-*-validated`)
  - post-deploy smoke test and automatic rollback to previous revision on failure
- **Rollback** (`.github/workflows/rollback-study-demo.yml`): manual approved traffic switch

Production (`tech-cartography-v9-signal-watch`) is never a deploy target. Browser acceptance remains manual after deploy.

See: `docs/v9_github_actions_cicd.md`
