"""Minimal Streamlit UI for Search Strategy Builder and BigQuery retrieval."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from tech_cartography.config import load_carbon_fiber_demo_profile
from tech_cartography.domain.search_profile import SearchProfile
from tech_cartography.reports.case_study_pipeline import (
  run_case_study_pipeline,
  save_case_study_outputs,
)
from tech_cartography.reports.claim_element_pipeline import (
  run_claim_element_pipeline,
  save_claim_element_outputs,
)
from tech_cartography.reports.claim_element_report import build_claim_element_summary
from tech_cartography.reports.paper_evidence_pipeline import (
  run_paper_evidence_pipeline,
  save_paper_evidence_outputs,
)
from tech_cartography.reports.paper_evidence_report import build_paper_evidence_summary
from tech_cartography.reports.fulltext_evidence_report import (
  build_fulltext_evidence_summary,
  render_fulltext_evidence_markdown,
)
from tech_cartography.reports.project_export import build_output_directory, load_records_csv
from tech_cartography.retrieval.bigquery_light_retriever import (
  RetrievalConfig,
  run_multi_query_retrieval,
)
from tech_cartography.retrieval.patent_fulltext_retriever import (
  FullTextRetrievalConfig,
  retrieve_fulltext_for_top_candidates,
  save_fulltext_collection_results,
)
from tech_cartography.retrieval.openalex_retriever import OpenAlexRetrievalConfig
from tech_cartography.strategy.query_plan import QueryPlan
from tech_cartography.strategy.search_strategy_builder import build_search_strategy


def _split_csv(value: str) -> list[str]:
  return [part.strip() for part in value.split(",") if part.strip()]


def render_search_strategy_page() -> None:
  st.title("PatentScout AI v7 — Carbon Fiber Evidence Map")
  st.caption("Phase 1-6: Strategy / BigQuery / Clustering / Full Text / Claim Elements / OpenAlex")

  if st.button("Load carbon fiber demo profile"):
    demo = load_carbon_fiber_demo_profile()
    st.session_state["theme"] = demo.theme
    st.session_state["materials"] = ", ".join(demo.materials)
    st.session_state["processes"] = ", ".join(demo.processes)
    st.session_state["properties"] = ", ".join(demo.properties)
    st.session_state["applications"] = ", ".join(demo.applications)
    st.session_state["companies"] = ", ".join(demo.companies)
    st.session_state["exclude_terms"] = ", ".join(demo.exclude_terms)

  theme = st.text_input("技術テーマ", key="theme")
  materials = st.text_input("対象材料 (comma-separated)", key="materials")
  processes = st.text_input("対象工程 (comma-separated)", key="processes")
  properties = st.text_input("対象物性 (comma-separated)", key="properties")
  applications = st.text_input("対象用途 (comma-separated)", key="applications")
  companies = st.text_input("対象企業 (comma-separated)", key="companies")
  exclude_terms = st.text_input("除外語 (comma-separated)", key="exclude_terms")

  if st.button("Build Search Strategy"):
    profile = SearchProfile.from_dict(
      {
        "theme": theme,
        "materials": _split_csv(materials),
        "processes": _split_csv(processes),
        "properties": _split_csv(properties),
        "applications": _split_csv(applications),
        "companies": _split_csv(companies),
        "exclude_terms": _split_csv(exclude_terms),
        "countries": ["JP", "US", "EP"],
        "year_min": 2010,
        "year_max": 2026,
      },
    )
    strategy = build_search_strategy(profile)
    st.session_state["strategy"] = strategy
    st.session_state["query_plans"] = [
      QueryPlan.from_dict(item) for item in strategy["query_plans"]
    ]

  strategy = st.session_state.get("strategy")
  if strategy:
    st.subheader("Recommended first plan")
    st.write(strategy.get("recommended_first_plan"))

    st.subheader("Query plans")
    for plan in strategy.get("query_plans", []):
      st.markdown(
        f"- **{plan['intent_id']}**: {plan['purpose']}  \n"
        f"  query_hint: `{plan['query_hint']}`",
      )

    st.subheader("BigQuery light retrieval")
    maximum_gb = st.number_input("maximum GB billed", min_value=1.0, value=300.0)
    max_total = st.number_input("max results total", min_value=100, value=2000, step=100)
    max_per_intent = st.number_input(
      "max results per intent",
      min_value=50,
      value=500,
      step=50,
    )
    execute_confirmed = st.checkbox("Execute BigQuery (not dry-run only)")

    if st.button("Run BigQuery dry run / retrieval"):
      query_plans = st.session_state.get("query_plans", [])
      config = RetrievalConfig(
        dry_run=not execute_confirmed,
        execute=execute_confirmed,
        maximum_bytes_billed_gb=float(maximum_gb),
        max_results_total=int(max_total),
        max_results_per_intent=int(max_per_intent),
        output_dir="outputs/bigquery_light_retrieval",
        use_cache=False,
      )
      retrieval = run_multi_query_retrieval(query_plans, config)
      st.session_state["retrieval"] = retrieval

    retrieval = st.session_state.get("retrieval")
    if retrieval:
      st.write(f"mode: {retrieval.get('mode')}")
      st.write(
        f"estimated GB: {retrieval.get('total_estimated_gb'):.4f} / "
        f"USD: {retrieval.get('total_estimated_usd'):.4f}",
      )
      st.write(f"records after dedup: {retrieval.get('total_records_after_dedup')}")
      st.write(f"output CSV: {retrieval.get('output_csv_path')}")

  st.subheader("Phase 3: Technology Clustering & Ranking")
  csv_path = st.text_input(
    "BigQuery dedup CSV path",
    value="outputs/bigquery_light_retrieval/latest/bigquery_light_results_dedup.csv",
  )
  uploaded = st.file_uploader("またはCSVアップロード", type=["csv"])

  if st.button("Run Technology Clustering"):
    if uploaded is not None:
      import io

      import pandas as pd

      records = pd.read_csv(uploaded).to_dict(orient="records")
    else:
      path = Path(csv_path)
      if not path.exists():
        parent = path.parent.parent
        candidates = sorted(parent.glob("*/bigquery_light_results_dedup.csv"))
        if candidates:
          path = candidates[-1]
      records = load_records_csv(path) if path.exists() else []

    if not records:
      st.error("入力CSVが見つかりません")
    else:
      result = run_case_study_pipeline(records, top_n=20, fulltext_top_n=5)
      output_dir = build_output_directory("outputs/carbon_fiber_case_study")
      paths = save_case_study_outputs(result, output_dir)
      st.session_state["case_study"] = {"result": result, "paths": paths}

  case_study = st.session_state.get("case_study")
  if case_study:
    result = case_study["result"]
    cluster_counts = {}
    for record in result["classified_records"]:
      cluster_counts[record["primary_cluster_id"]] = cluster_counts.get(record["primary_cluster_id"], 0) + 1
    st.write("クラスタ別件数:", cluster_counts)
    st.dataframe(result["top_records"])
    st.subheader("Top5全文取得候補")
    st.dataframe(result["fulltext_candidates"])
    st.subheader("Evidence Map Report")
    st.markdown(result["markdown"])
    st.write("保存先:", case_study["paths"])

  st.subheader("Phase 4: Top5 Full Text Evidence Collection")
  top5_csv_path = st.text_input(
    "top5_fulltext_candidates.csv path",
    value="outputs/carbon_fiber_case_study/latest/top5_fulltext_candidates.csv",
  )
  top5_uploaded = st.file_uploader("またはTop5 CSVアップロード", type=["csv"], key="top5_csv")
  ft_max_gb = st.number_input("full text maximum GB", min_value=1.0, value=50.0, key="ft_max_gb")
  ft_execute = st.checkbox("Execute BigQuery full text", key="ft_execute")
  ft_use_cache = st.checkbox("Use full text cache", value=True, key="ft_use_cache")

  if st.button("Run Top5 Full Text Collection"):
    if top5_uploaded is not None:
      import pandas as pd

      candidates = pd.read_csv(top5_uploaded).to_dict(orient="records")
    else:
      path = Path(top5_csv_path)
      if not path.exists():
        parent = path.parent.parent
        candidates_paths = sorted(parent.glob("*/top5_fulltext_candidates.csv"))
        if candidates_paths:
          path = candidates_paths[-1]
      candidates = load_records_csv(path) if path.exists() else []

    if not candidates:
      st.error("Top5 CSVが見つかりません")
    else:
      ft_config = FullTextRetrievalConfig(
        dry_run=not ft_execute,
        execute=ft_execute,
        maximum_bytes_billed_gb=float(ft_max_gb),
        use_cache=ft_use_cache,
      )
      ft_result = retrieve_fulltext_for_top_candidates(candidates, ft_config)
      ft_summary = build_fulltext_evidence_summary(ft_result)
      ft_markdown = render_fulltext_evidence_markdown(ft_summary)
      ft_paths = save_fulltext_collection_results(
        ft_result.get("retrieved_records", []),
        ft_config.output_dir,
        summary=ft_result,
        manual_records=ft_result.get("manual_required_records", []),
        markdown=ft_markdown,
      )
      st.session_state["fulltext_collection"] = {
        "result": ft_result,
        "summary": ft_summary,
        "markdown": ft_markdown,
        "paths": ft_paths,
      }

  fulltext_collection = st.session_state.get("fulltext_collection")
  if fulltext_collection:
    ft_result = fulltext_collection["result"]
    st.write(f"mode: {ft_result.get('mode')}")
    st.write(
      f"estimated GB: {ft_result.get('total_estimated_gb', 0):.4f} / "
      f"USD: {ft_result.get('total_estimated_usd', 0):.4f}",
    )
    st.write(f"cache hits: {ft_result.get('cache_hits')}")
    st.write(f"manual required: {ft_result.get('manual_required_candidates')}")
    st.dataframe(ft_result.get("retrieved_records", []))
    st.subheader("Manual required")
    st.dataframe(ft_result.get("manual_required_records", []))
    st.markdown(fulltext_collection["markdown"])
    st.write("保存先:", fulltext_collection["paths"])

  st.subheader("Phase 5: Claim Element Extraction")
  top5_json_path = st.text_input(
    "top5_fulltext_records.json path",
    value="outputs/top5_fulltext_collection/latest/top5_fulltext_records.json",
    key="phase5_json_path",
  )
  top5_json_uploaded = st.file_uploader(
    "またはTop5 full text JSONアップロード",
    type=["json"],
    key="top5_json",
  )

  if st.button("Run Claim Element Extraction"):
    if top5_json_uploaded is not None:
      records = json.loads(top5_json_uploaded.getvalue().decode("utf-8"))
      if isinstance(records, dict):
        records = records.get("retrieved_records", [])
    else:
      path = Path(top5_json_path)
      if not path.exists():
        parent = path.parent.parent
        candidates = sorted(parent.glob("*/top5_fulltext_records.json"))
        if candidates:
          path = candidates[-1]
      if path.exists():
        with path.open(encoding="utf-8") as handle:
          data = json.load(handle)
        records = data if isinstance(data, list) else data.get("retrieved_records", [])
      else:
        records = []

    if not records:
      st.error("top5_fulltext_records.json が見つかりません")
    else:
      ce_result = run_claim_element_pipeline(records)
      ce_output_dir = build_output_directory("outputs/claim_element_extraction")
      ce_paths = save_claim_element_outputs(ce_result, ce_output_dir)
      ce_summary = build_claim_element_summary(ce_result)
      st.session_state["claim_element_extraction"] = {
        "result": ce_result,
        "summary": ce_summary,
        "paths": ce_paths,
      }

  claim_element_extraction = st.session_state.get("claim_element_extraction")
  if claim_element_extraction:
    ce_summary = claim_element_extraction["summary"]
    st.write("element type別件数:", ce_summary.get("element_type_counts", {}))
    st.write("support status別件数:", ce_summary.get("support_status_counts", {}))
    st.subheader("Paper query candidates")
    st.dataframe(claim_element_extraction["result"].get("paper_queries", []))
    report_path = claim_element_extraction["paths"].get("claim_element_report_md")
    if report_path and Path(report_path).exists():
      st.subheader("Claim Element Report")
      st.markdown(Path(report_path).read_text(encoding="utf-8"))
    st.write("保存先:", claim_element_extraction["paths"])

  st.subheader("Phase 6: OpenAlex Paper Evidence Search")
  paper_query_csv_path = st.text_input(
    "paper_query_candidates.csv path",
    value="outputs/claim_element_extraction/latest/paper_query_candidates.csv",
    key="phase6_query_csv",
  )
  claim_elements_csv_path = st.text_input(
    "claim_elements.csv path",
    value="outputs/claim_element_extraction/latest/claim_elements.csv",
    key="phase6_elements_csv",
  )
  oa_max_queries = st.number_input("max queries", min_value=1, value=20, key="oa_max_queries")
  oa_max_results = st.number_input(
    "max results per query",
    min_value=1,
    value=10,
    key="oa_max_results",
  )
  oa_execute = st.checkbox("Execute OpenAlex", key="oa_execute")
  oa_use_cache = st.checkbox("Use OpenAlex cache", value=True, key="oa_use_cache")
  oa_polite_email = st.text_input("polite email (optional)", key="oa_polite_email")

  if st.button("Run OpenAlex Paper Evidence Search"):
    query_path = Path(paper_query_csv_path)
    elements_path = Path(claim_elements_csv_path)
    for path, pattern in (
      (query_path, "paper_query_candidates.csv"),
      (elements_path, "claim_elements.csv"),
    ):
      if not path.exists() and "latest" in str(path):
        parent = path.parent.parent
        candidates = sorted(parent.glob(f"*/{pattern}"))
        if candidates:
          path = candidates[-1]
    query_rows = load_records_csv(query_path) if query_path.exists() else []
    claim_elements = load_records_csv(elements_path) if elements_path.exists() else []
    if not query_rows:
      st.error("paper_query_candidates.csv が見つかりません")
    else:
      oa_config = OpenAlexRetrievalConfig(
        execute=oa_execute,
        max_queries=int(oa_max_queries),
        max_results_per_query=int(oa_max_results),
        use_cache=oa_use_cache,
        polite_email=oa_polite_email or None,
      )
      oa_result = run_paper_evidence_pipeline(query_rows, claim_elements, oa_config)
      oa_output_dir = build_output_directory("outputs/openalex_paper_evidence")
      oa_paths = save_paper_evidence_outputs(oa_result, oa_output_dir)
      oa_summary = build_paper_evidence_summary(oa_result)
      st.session_state["paper_evidence"] = {
        "result": oa_result,
        "summary": oa_summary,
        "paths": oa_paths,
      }

  paper_evidence = st.session_state.get("paper_evidence")
  if paper_evidence:
    oa_summary = paper_evidence["summary"]
    st.write(f"mode: {paper_evidence['result'].get('mode')}")
    st.write("source quality集計:", oa_summary.get("source_quality_counts", {}))
    st.subheader("Paper evidence links")
    st.dataframe(paper_evidence["result"].get("evidence_links", []))
    report_path = paper_evidence["paths"].get("paper_evidence_report_md")
    if report_path and Path(report_path).exists():
      st.subheader("Paper Evidence Report")
      st.markdown(Path(report_path).read_text(encoding="utf-8"))
    st.write("保存先:", paper_evidence["paths"])

  if strategy:
    with st.expander("Full strategy JSON"):
      st.code(json.dumps(strategy, indent=2, ensure_ascii=False), language="json")


def main() -> None:
  render_search_strategy_page()


if __name__ == "__main__":
  main()
