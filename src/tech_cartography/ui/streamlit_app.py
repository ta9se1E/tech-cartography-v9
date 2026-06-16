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
from tech_cartography.reports.project_export import build_output_directory, load_records_csv
from tech_cartography.retrieval.bigquery_light_retriever import (
  RetrievalConfig,
  run_multi_query_retrieval,
)
from tech_cartography.strategy.query_plan import QueryPlan
from tech_cartography.strategy.search_strategy_builder import build_search_strategy


def _split_csv(value: str) -> list[str]:
  return [part.strip() for part in value.split(",") if part.strip()]


def render_search_strategy_page() -> None:
  st.title("PatentScout AI v7 — Carbon Fiber Evidence Map")
  st.caption("Phase 1-3: Strategy / BigQuery Light / Clustering & Ranking")

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

  if strategy:
    with st.expander("Full strategy JSON"):
      st.code(json.dumps(strategy, indent=2, ensure_ascii=False), language="json")


def main() -> None:
  render_search_strategy_page()


if __name__ == "__main__":
  main()
