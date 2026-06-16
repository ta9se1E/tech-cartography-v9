"""Minimal Streamlit UI for Search Strategy Builder and BigQuery retrieval."""

from __future__ import annotations

import json

import streamlit as st

from tech_cartography.config import load_carbon_fiber_demo_profile
from tech_cartography.domain.search_profile import SearchProfile
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
  st.caption("Phase 1 Search Strategy / Phase 2 BigQuery Light Retrieval")

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
  if not strategy:
    return

  st.subheader("Recommended first plan")
  st.write(strategy.get("recommended_first_plan"))

  st.subheader("Query plans")
  for plan in strategy.get("query_plans", []):
    st.markdown(
      f"- **{plan['intent_id']}**: {plan['purpose']}  \n"
      f"  query_hint: `{plan['query_hint']}`",
    )

  st.subheader("Warnings")
  st.write(strategy.get("warnings") or ["None"])

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
    st.write(f"records before dedup: {retrieval.get('total_records_before_dedup')}")
    st.write(f"records after dedup: {retrieval.get('total_records_after_dedup')}")
    st.write(f"output CSV: {retrieval.get('output_csv_path')}")

  with st.expander("Full strategy JSON"):
    st.code(json.dumps(strategy, indent=2, ensure_ascii=False), language="json")


def main() -> None:
  render_search_strategy_page()


if __name__ == "__main__":
  main()
