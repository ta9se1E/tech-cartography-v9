"""Minimal Streamlit UI for Search Strategy Builder."""

from __future__ import annotations

import json

import streamlit as st

from tech_cartography.config import load_carbon_fiber_demo_profile
from tech_cartography.domain.search_profile import SearchProfile
from tech_cartography.strategy.search_strategy_builder import build_search_strategy


def _split_csv(value: str) -> list[str]:
  return [part.strip() for part in value.split(",") if part.strip()]


def render_search_strategy_page() -> None:
  st.title("PatentScout AI v7 — Search Strategy Builder")
  st.caption("Carbon Fiber Evidence Map / Phase 1")

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

  strategy = st.session_state.get("strategy")
  if not strategy:
    return

  st.subheader("Recommended first plan")
  st.write(strategy.get("recommended_first_plan"))

  st.subheader("Warnings")
  st.write(strategy.get("warnings") or ["None"])

  st.subheader("Next actions")
  for action in strategy.get("next_actions", []):
    st.write(f"- {action}")

  st.subheader("Generated query plans")
  st.json(strategy.get("query_plans", []))

  with st.expander("Full strategy JSON"):
    st.code(json.dumps(strategy, indent=2, ensure_ascii=False), language="json")


def main() -> None:
  render_search_strategy_page()


if __name__ == "__main__":
  main()
