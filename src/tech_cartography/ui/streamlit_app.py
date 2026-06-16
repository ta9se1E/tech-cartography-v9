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
from tech_cartography.evidence.claim_paper_evidence_map import build_claim_paper_evidence_map
from tech_cartography.reports.claim_paper_evidence_map_report import build_claim_paper_evidence_map_summary
from tech_cartography.reports.evidence_map_export import save_claim_paper_evidence_map_outputs
from tech_cartography.agents.technical_view_agent import run_technical_view_assessment
from tech_cartography.reports.technical_assessment_export import save_technical_view_outputs
from tech_cartography.reports.technical_view_report import build_technical_view_summary
from tech_cartography.ingestion.web_signal_loader import load_web_signal_file, save_demo_web_signal_template
from tech_cartography.reports.web_signal_export import run_web_signal_mapping, save_web_signal_outputs
from tech_cartography.reports.web_signal_report import build_web_signal_summary
from tech_cartography.agents.business_view_agent import run_business_view_assessment
from tech_cartography.reports.business_assessment_export import save_business_view_outputs
from tech_cartography.reports.business_view_report import build_business_view_summary
from tech_cartography.agents.synthesis_agent import run_synthesis_report
from tech_cartography.reports.synthesis_export import save_synthesis_outputs
from tech_cartography.reports.synthesis_report import build_synthesis_report_summary
from tech_cartography.reports.fulltext_evidence_report import (
  build_fulltext_evidence_summary,
  render_fulltext_evidence_markdown,
)
from tech_cartography.reports.paper_evidence_report import build_paper_evidence_summary
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


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _split_csv(value: str) -> list[str]:
  return [part.strip() for part in value.split(",") if part.strip()]


def render_search_strategy_page() -> None:
  st.title("PatentScout AI v7 — Carbon Fiber Evidence Map")
  st.caption("Phase 1-11: Strategy / BigQuery / Clustering / Full Text / Claims / OpenAlex / Evidence Map / Technical View / Web Signals / Business View / Synthesis Report")

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

  st.subheader("Phase 7: Claim × Paper Evidence Map")
  map_claim_csv = st.text_input(
    "claim_elements.csv path",
    value="outputs/claim_element_extraction/latest/claim_elements.csv",
    key="phase7_claim_csv",
  )
  map_links_csv = st.text_input(
    "paper_evidence_links.csv path",
    value="outputs/openalex_paper_evidence/latest/paper_evidence_links.csv",
    key="phase7_links_csv",
  )
  map_records_csv = st.text_input(
    "paper_records_dedup.csv path",
    value="outputs/openalex_paper_evidence/latest/paper_records_dedup.csv",
    key="phase7_records_csv",
  )
  map_quality_csv = st.text_input(
    "source_quality_results.csv path",
    value="outputs/openalex_paper_evidence/latest/source_quality_results.csv",
    key="phase7_quality_csv",
  )
  map_top_n = st.number_input("top evidence items", min_value=5, value=30, key="phase7_top_n")

  if st.button("Build Claim × Paper Evidence Map"):
    paths_and_patterns = [
      (Path(map_claim_csv), "claim_elements.csv"),
      (Path(map_links_csv), "paper_evidence_links.csv"),
      (Path(map_records_csv), "paper_records_dedup.csv"),
      (Path(map_quality_csv), "source_quality_results.csv"),
    ]
    resolved: list[Path] = []
    for path, pattern in paths_and_patterns:
      if not path.exists() and "latest" in str(path):
        parent = path.parent.parent
        candidates = sorted(parent.glob(f"*/{pattern}"))
        if candidates:
          path = candidates[-1]
      resolved.append(path)

    claim_elements = load_records_csv(resolved[0]) if resolved[0].exists() else []
    paper_links = load_records_csv(resolved[1]) if resolved[1].exists() else []
    paper_records = load_records_csv(resolved[2]) if resolved[2].exists() else []
    source_quality = load_records_csv(resolved[3]) if resolved[3].exists() else []

    if not claim_elements:
      st.error("claim_elements.csv が見つかりません")
    else:
      map_result = build_claim_paper_evidence_map(
        claim_elements,
        paper_links,
        paper_records=paper_records,
        source_quality_results=source_quality,
      )
      map_output_dir = build_output_directory("outputs/claim_paper_evidence_map")
      map_paths = save_claim_paper_evidence_map_outputs(
        map_result,
        map_output_dir,
        top_n=int(map_top_n),
      )
      map_summary = build_claim_paper_evidence_map_summary(map_result)
      st.session_state["claim_paper_evidence_map"] = {
        "result": map_result,
        "summary": map_summary,
        "paths": map_paths,
      }

  claim_paper_evidence_map = st.session_state.get("claim_paper_evidence_map")
  if claim_paper_evidence_map:
    map_summary = claim_paper_evidence_map["summary"]
    st.write("summary:", {
      "patents": map_summary.get("total_patents"),
      "claim elements": map_summary.get("total_claim_elements"),
      "evidence items": map_summary.get("total_evidence_items"),
      "supporting": map_summary.get("supporting_evidence_candidates"),
      "no paper evidence": map_summary.get("no_paper_evidence"),
    })
    st.subheader("Patent-level evidence maps")
    st.dataframe(claim_paper_evidence_map["result"].get("patent_evidence_maps", []))
    st.subheader("Top evidence items")
    st.dataframe(claim_paper_evidence_map["result"].get("top_evidence_items", []))
    st.subheader("Evidence gaps")
    st.dataframe(claim_paper_evidence_map["result"].get("evidence_gaps", []))
    report_path = claim_paper_evidence_map["paths"].get("claim_paper_evidence_map_report_md")
    if report_path and Path(report_path).exists():
      st.subheader("Claim × Paper Evidence Map Report")
      st.markdown(Path(report_path).read_text(encoding="utf-8"))
    st.write("保存先:", claim_paper_evidence_map["paths"])

  st.subheader("Phase 8: Technical View Agent")
  tv_maps_json = st.text_input(
    "patent_evidence_maps.json path",
    value="outputs/claim_paper_evidence_map/latest/patent_evidence_maps.json",
    key="phase8_maps_json",
  )
  tv_items_csv = st.text_input(
    "claim_paper_evidence_items.csv path",
    value="outputs/claim_paper_evidence_map/latest/claim_paper_evidence_items.csv",
    key="phase8_items_csv",
  )
  tv_gaps_csv = st.text_input(
    "evidence_gaps.csv path",
    value="outputs/claim_paper_evidence_map/latest/evidence_gaps.csv",
    key="phase8_gaps_csv",
  )
  tv_claim_csv = st.text_input(
    "claim_elements.csv (optional)",
    value="outputs/claim_element_extraction/latest/claim_elements.csv",
    key="phase8_claim_csv",
  )
  tv_fulltext_json = st.text_input(
    "top5_fulltext_records.json (optional)",
    value="outputs/top5_fulltext_collection/latest/top5_fulltext_records.json",
    key="phase8_fulltext_json",
  )

  if st.button("Run Technical View Agent"):
    def _resolve(path: Path, pattern: str) -> Path:
      if not path.exists() and "latest" in str(path):
        parent = path.parent.parent
        candidates = sorted(parent.glob(f"*/{pattern}"))
        if candidates:
          return candidates[-1]
      return path

    maps_path = _resolve(Path(tv_maps_json), "patent_evidence_maps.json")
    items_path = _resolve(Path(tv_items_csv), "claim_paper_evidence_items.csv")
    gaps_path = _resolve(Path(tv_gaps_csv), "evidence_gaps.csv")
    claim_path = _resolve(Path(tv_claim_csv), "claim_elements.csv")
    fulltext_path = _resolve(Path(tv_fulltext_json), "top5_fulltext_records.json")

    if maps_path.exists():
      with maps_path.open(encoding="utf-8") as handle:
        patent_maps = json.load(handle)
      if isinstance(patent_maps, dict):
        patent_maps = patent_maps.get("patent_evidence_maps", [])
    else:
      patent_maps = []

    evidence_items = load_records_csv(items_path) if items_path.exists() else []
    evidence_gaps = load_records_csv(gaps_path) if gaps_path.exists() else []
    claim_elements = load_records_csv(claim_path) if claim_path.exists() else None
    fulltext_records = None
    if fulltext_path.exists():
      with fulltext_path.open(encoding="utf-8") as handle:
        fulltext_data = json.load(handle)
      fulltext_records = (
        fulltext_data if isinstance(fulltext_data, list) else fulltext_data.get("retrieved_records", [])
      )

    if not patent_maps:
      st.error("patent_evidence_maps.json が見つかりません")
    else:
      tv_result = run_technical_view_assessment(
        patent_maps,
        evidence_items,
        evidence_gaps,
        claim_elements=claim_elements,
        fulltext_records=fulltext_records,
      )
      tv_output_dir = build_output_directory("outputs/technical_view_assessment")
      tv_paths = save_technical_view_outputs(tv_result, tv_output_dir)
      tv_summary = build_technical_view_summary(tv_result)
      st.session_state["technical_view"] = {
        "result": tv_result,
        "summary": tv_summary,
        "paths": tv_paths,
      }

  technical_view = st.session_state.get("technical_view")
  if technical_view:
    tv_summary = technical_view["summary"]
    st.write(
      "confidence counts:",
      {
        "high": tv_summary.get("high_confidence"),
        "medium": tv_summary.get("medium_confidence"),
        "low": tv_summary.get("low_confidence"),
        "human_review_required": tv_summary.get("human_review_required"),
      },
    )
    st.subheader("Patent technical summaries")
    st.dataframe(
      [
        {
          "publication_number": a.get("publication_number"),
          "overall_technical_confidence": a.get("overall_technical_confidence"),
          "overall_technical_score": a.get("overall_technical_score"),
          "technical_summary": a.get("technical_summary"),
          "recommended_reader_action": a.get("recommended_reader_action"),
        }
        for a in technical_view["result"].get("technical_assessments", [])
      ],
    )
    st.subheader("Common technical risks")
    st.write(technical_view["result"].get("common_technical_risks", {}))
    report_path = technical_view["paths"].get("technical_view_report_md")
    if report_path and Path(report_path).exists():
      st.subheader("Technical View Report")
      st.markdown(Path(report_path).read_text(encoding="utf-8"))
    st.write("保存先:", technical_view["paths"])

  st.subheader("Phase 9: Web / Company Signal Mapping")
  ws_file_path = st.text_input(
    "web signal CSV/JSON/YAML path",
    value="case_studies/carbon_fiber/web_signals/carbon_fiber_web_signals_template.csv",
    key="phase9_ws_file",
  )
  ws_patents_csv = st.text_input(
    "patents CSV path",
    value="outputs/carbon_fiber_case_study/latest/top20_patents.csv",
    key="phase9_patents_csv",
  )
  ws_uploaded = st.file_uploader("またはWeb signalファイルアップロード", type=["csv", "json", "yaml", "yml"], key="phase9_ws_upload")
  ws_patents_uploaded = st.file_uploader("またはpatents CSVアップロード", type=["csv"], key="phase9_patents_upload")

  if st.button("Generate Web Signal Template CSV"):
    template_path = save_demo_web_signal_template("case_studies/carbon_fiber/web_signals")
    st.success(f"Template saved: {template_path}")

  if st.button("Run Web Signal Mapping"):
    if ws_uploaded is not None:
      import tempfile

      suffix = Path(ws_uploaded.name).suffix or ".csv"
      with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(ws_uploaded.getvalue())
        tmp_path = tmp.name
      signals = load_web_signal_file(tmp_path)
    else:
      ws_path = Path(ws_file_path)
      if not ws_path.exists():
        ws_path = PROJECT_ROOT / ws_file_path if "case_studies" in ws_file_path else ws_path
      signals = load_web_signal_file(str(ws_path)) if ws_path.exists() else []

    if ws_patents_uploaded is not None:
      import pandas as pd

      patents = pd.read_csv(ws_patents_uploaded).to_dict(orient="records")
    else:
      patents_path = Path(ws_patents_csv)
      if not patents_path.exists() and "latest" in str(patents_path):
        parent = patents_path.parent.parent
        candidates = sorted(parent.glob("*/top20_patents.csv")) or sorted(parent.glob("*/ranked_patents.csv"))
        if candidates:
          patents_path = candidates[-1]
      patents = load_records_csv(patents_path) if patents_path.exists() else []

    if not signals:
      st.error("Web signalファイルが見つかりません")
    elif not patents:
      st.error("patents CSVが見つかりません")
    else:
      ws_result = run_web_signal_mapping(signals, patents)
      ws_output_dir = build_output_directory("outputs/web_signal_mapping")
      ws_paths = save_web_signal_outputs(ws_result, ws_output_dir)
      ws_summary = build_web_signal_summary(ws_result)
      st.session_state["web_signal_mapping"] = {
        "result": ws_result,
        "summary": ws_summary,
        "paths": ws_paths,
      }

  web_signal_mapping = st.session_state.get("web_signal_mapping")
  if web_signal_mapping:
    ws_summary = web_signal_mapping["summary"]
    st.write(
      "summary:",
      {
        "signals": ws_summary.get("signals_loaded"),
        "patent links": ws_summary.get("patent_links"),
        "business candidates": ws_summary.get("business_signal_candidates"),
        "background": ws_summary.get("background_signals"),
      },
    )
    st.subheader("Signals by company")
    st.dataframe(web_signal_mapping["result"].get("by_company", []))
    st.subheader("Signals by cluster")
    st.dataframe(web_signal_mapping["result"].get("by_cluster", []))
    st.subheader("Patent links")
    st.dataframe(web_signal_mapping["result"].get("links", []))
    report_path = web_signal_mapping["paths"].get("web_signal_report_md")
    if report_path and Path(report_path).exists():
      st.subheader("Web Signal Report")
      st.markdown(Path(report_path).read_text(encoding="utf-8"))
    st.write("保存先:", web_signal_mapping["paths"])

  st.subheader("Phase 10: Business View Agent")
  bv_tech_json = st.text_input(
    "technical_assessments.json path",
    value="outputs/technical_view_assessment/latest/technical_assessments.json",
    key="phase10_tech_json",
  )
  bv_tech_csv = st.text_input(
    "patent_technical_summary.csv path",
    value="outputs/technical_view_assessment/latest/patent_technical_summary.csv",
    key="phase10_tech_csv",
  )
  bv_web_csv = st.text_input(
    "web_signal_patent_links.csv path",
    value="outputs/web_signal_mapping/latest/web_signal_patent_links.csv",
    key="phase10_web_csv",
  )
  bv_ranked_csv = st.text_input(
    "ranked_patents.csv (optional)",
    value="outputs/carbon_fiber_case_study/latest/ranked_patents.csv",
    key="phase10_ranked_csv",
  )
  bv_maps_json = st.text_input(
    "patent_evidence_maps.json (optional)",
    value="outputs/claim_paper_evidence_map/latest/patent_evidence_maps.json",
    key="phase10_maps_json",
  )
  bv_tech_upload = st.file_uploader("または technical_assessments.json アップロード", type=["json"], key="phase10_tech_upload")
  bv_summary_upload = st.file_uploader("または patent_technical_summary.csv アップロード", type=["csv"], key="phase10_summary_upload")
  bv_web_upload = st.file_uploader("または web_signal_patent_links.csv アップロード", type=["csv"], key="phase10_web_upload")

  if st.button("Run Business View Agent", key="phase10_run_button"):
    def _resolve_bv(path: Path, pattern: str) -> Path:
      if not path.exists() and "latest" in str(path):
        parent = path.parent.parent
        candidates = sorted(parent.glob(f"*/{pattern}"))
        if candidates:
          return candidates[-1]
      return path

    tech_json_path = _resolve_bv(Path(bv_tech_json), "technical_assessments.json")
    tech_csv_path = _resolve_bv(Path(bv_tech_csv), "patent_technical_summary.csv")
    web_csv_path = _resolve_bv(Path(bv_web_csv), "web_signal_patent_links.csv")
    ranked_path = _resolve_bv(Path(bv_ranked_csv), "ranked_patents.csv")
    maps_path = _resolve_bv(Path(bv_maps_json), "patent_evidence_maps.json")

    if bv_tech_upload is not None:
      tmp = Path("outputs/_uploads/technical_assessments.json")
      tmp.parent.mkdir(parents=True, exist_ok=True)
      tmp.write_bytes(bv_tech_upload.getvalue())
      tech_json_path = tmp
    if bv_summary_upload is not None:
      tmp = Path("outputs/_uploads/patent_technical_summary.csv")
      tmp.parent.mkdir(parents=True, exist_ok=True)
      tmp.write_bytes(bv_summary_upload.getvalue())
      tech_csv_path = tmp
    if bv_web_upload is not None:
      tmp = Path("outputs/_uploads/web_signal_patent_links.csv")
      tmp.parent.mkdir(parents=True, exist_ok=True)
      tmp.write_bytes(bv_web_upload.getvalue())
      web_csv_path = tmp

    technical_assessments: list[dict] = []
    if tech_json_path.exists():
      with tech_json_path.open(encoding="utf-8") as handle:
        technical_assessments = json.load(handle)
      if not isinstance(technical_assessments, list):
        technical_assessments = []

    patent_technical_summary = load_records_csv(tech_csv_path) if tech_csv_path.exists() else []
    web_signal_links = load_records_csv(web_csv_path) if web_csv_path.exists() else []
    ranked_patents = load_records_csv(ranked_path) if ranked_path.exists() else None
    patent_evidence_maps = None
    if maps_path.exists():
      with maps_path.open(encoding="utf-8") as handle:
        maps_data = json.load(handle)
      patent_evidence_maps = maps_data if isinstance(maps_data, list) else maps_data.get("patent_evidence_maps", [])

    if not patent_technical_summary and not technical_assessments:
      st.error("technical_assessments.json または patent_technical_summary.csv が必要です")
    else:
      bv_result = run_business_view_assessment(
        technical_assessments,
        patent_technical_summary,
        web_signal_links,
        ranked_patents=ranked_patents,
        patent_evidence_maps=patent_evidence_maps,
      )
      bv_output_dir = build_output_directory("outputs/business_view_assessment")
      bv_paths = save_business_view_outputs(bv_result, bv_output_dir)
      bv_summary = build_business_view_summary(bv_result)
      st.session_state["business_view"] = {
        "result": bv_result,
        "summary": bv_summary,
        "paths": bv_paths,
      }

  business_view = st.session_state.get("business_view")
  if business_view:
    bv_summary = business_view["summary"]
    st.write(
      "business priority counts:",
      {
        "high": business_view["result"].get("high_business_priority_patents"),
        "medium": business_view["result"].get("medium_business_priority_patents"),
        "low": business_view["result"].get("low_business_priority_patents"),
        "monitor_only": business_view["result"].get("monitor_only_patents"),
        "expert_review_required": business_view["result"].get("expert_review_required"),
      },
    )
    st.subheader("SME opportunity candidates")
    st.dataframe(business_view["result"].get("sme_opportunity_candidates", []))
    st.subheader("Design-around candidates")
    st.dataframe(business_view["result"].get("design_around_candidates", []))
    st.subheader("Patent business summary")
    st.dataframe(
      [
        {
          "publication_number": a.get("publication_number"),
          "overall_business_confidence": a.get("overall_business_confidence"),
          "overall_business_score": a.get("overall_business_score"),
          "business_summary": a.get("business_summary"),
          "recommended_reader_action": a.get("recommended_reader_action"),
        }
        for a in business_view["result"].get("business_assessments", [])
      ],
    )
    report_path = business_view["paths"].get("business_view_report_md")
    if report_path and Path(report_path).exists():
      st.subheader("Business View Report")
      st.markdown(Path(report_path).read_text(encoding="utf-8"))
    st.write("保存先:", business_view["paths"])

  st.subheader("Phase 11: Synthesis Report")
  syn_cluster_json = st.text_input(
    "cluster_summary.json path",
    value="outputs/carbon_fiber_case_study/latest/cluster_summary.json",
    key="phase11_cluster_json",
  )
  syn_top20_csv = st.text_input(
    "top20_patents.csv path",
    value="outputs/carbon_fiber_case_study/latest/top20_patents.csv",
    key="phase11_top20_csv",
  )
  syn_top5_csv = st.text_input(
    "top5_fulltext_candidates.csv path",
    value="outputs/carbon_fiber_case_study/latest/top5_fulltext_candidates.csv",
    key="phase11_top5_csv",
  )
  syn_tech_json = st.text_input(
    "technical_assessments.json path",
    value="outputs/technical_view_assessment/latest/technical_assessments.json",
    key="phase11_tech_json",
  )
  syn_tech_csv = st.text_input(
    "patent_technical_summary.csv path",
    value="outputs/technical_view_assessment/latest/patent_technical_summary.csv",
    key="phase11_tech_csv",
  )
  syn_biz_json = st.text_input(
    "business_assessments.json path",
    value="outputs/business_view_assessment/latest/business_assessments.json",
    key="phase11_biz_json",
  )
  syn_biz_csv = st.text_input(
    "patent_business_summary.csv path",
    value="outputs/business_view_assessment/latest/patent_business_summary.csv",
    key="phase11_biz_csv",
  )
  syn_theme = st.text_input("theme", value="PAN系炭素繊維の中温域炭化条件最適化", key="phase11_theme")
  syn_claim_paper_json = st.text_input(
    "claim_paper_evidence_map_summary.json (optional)",
    value="outputs/claim_paper_evidence_map/latest/claim_paper_evidence_map_summary.json",
    key="phase11_claim_paper_json",
  )
  syn_gaps_csv = st.text_input(
    "evidence_gaps.csv (optional)",
    value="outputs/claim_paper_evidence_map/latest/evidence_gaps.csv",
    key="phase11_gaps_csv",
  )
  syn_company_csv = st.text_input(
    "web_signals_by_company.csv (optional)",
    value="outputs/web_signal_mapping/latest/web_signals_by_company.csv",
    key="phase11_company_csv",
  )

  if st.button("Build Synthesis Report", key="phase11_run_button"):
    def _resolve_syn(path: Path, pattern: str) -> Path:
      if not path.exists() and "latest" in str(path):
        parent = path.parent.parent
        candidates = sorted(parent.glob(f"*/{pattern}"))
        if candidates:
          return candidates[-1]
      return path

    cluster_path = _resolve_syn(Path(syn_cluster_json), "cluster_summary.json")
    top20_path = _resolve_syn(Path(syn_top20_csv), "top20_patents.csv")
    top5_path = _resolve_syn(Path(syn_top5_csv), "top5_fulltext_candidates.csv")
    tech_json_path = _resolve_syn(Path(syn_tech_json), "technical_assessments.json")
    tech_csv_path = _resolve_syn(Path(syn_tech_csv), "patent_technical_summary.csv")
    biz_json_path = _resolve_syn(Path(syn_biz_json), "business_assessments.json")
    biz_csv_path = _resolve_syn(Path(syn_biz_csv), "patent_business_summary.csv")
    claim_paper_path = _resolve_syn(Path(syn_claim_paper_json), "claim_paper_evidence_map_summary.json")
    gaps_path = _resolve_syn(Path(syn_gaps_csv), "evidence_gaps.csv")
    company_path = _resolve_syn(Path(syn_company_csv), "web_signals_by_company.csv")

    cluster_data = json.loads(cluster_path.read_text(encoding="utf-8")) if cluster_path.exists() else {}
    cluster_summary = cluster_data.get("clusters", []) if isinstance(cluster_data, dict) else []
    top20_patents = load_records_csv(top20_path) if top20_path.exists() else []
    top5_candidates = load_records_csv(top5_path) if top5_path.exists() else []
    technical_assessments = json.loads(tech_json_path.read_text(encoding="utf-8")) if tech_json_path.exists() else []
    if not isinstance(technical_assessments, list):
      technical_assessments = []
    patent_technical_summary = load_records_csv(tech_csv_path) if tech_csv_path.exists() else []
    business_assessments = json.loads(biz_json_path.read_text(encoding="utf-8")) if biz_json_path.exists() else []
    if not isinstance(business_assessments, list):
      business_assessments = []
    patent_business_summary = load_records_csv(biz_csv_path) if biz_csv_path.exists() else []
    claim_paper_summary = json.loads(claim_paper_path.read_text(encoding="utf-8")) if claim_paper_path.exists() else None
    evidence_gaps = load_records_csv(gaps_path) if gaps_path.exists() else None
    web_signals_by_company = load_records_csv(company_path) if company_path.exists() else None

    if not top20_patents:
      st.error("top20_patents.csv が見つかりません")
    else:
      syn_result = run_synthesis_report(
        cluster_summary,
        top20_patents,
        top5_candidates,
        technical_assessments,
        patent_technical_summary,
        business_assessments,
        patent_business_summary,
        claim_paper_summary=claim_paper_summary,
        evidence_gaps=evidence_gaps,
        web_signals_by_company=web_signals_by_company,
        theme=syn_theme,
      )
      syn_output_dir = build_output_directory("outputs/synthesis_report")
      syn_paths = save_synthesis_outputs(syn_result, syn_output_dir)
      syn_summary = build_synthesis_report_summary(syn_result)
      st.session_state["synthesis_report"] = {
        "result": syn_result,
        "summary": syn_summary,
        "paths": syn_paths,
      }

  synthesis_report = st.session_state.get("synthesis_report")
  if synthesis_report:
    st.subheader("Executive Summary")
    st.write(synthesis_report["result"].get("executive_summary"))
    st.subheader("Key Findings")
    st.dataframe(synthesis_report["result"].get("key_findings", []))
    st.subheader("Priority Patents")
    st.dataframe(synthesis_report["result"].get("priority_patents", []))
    st.subheader("SME Action Plan")
    st.json(synthesis_report["result"].get("sme_action_plan", []))
    st.subheader("Next Update Recommendations")
    st.write(synthesis_report["result"].get("next_update_recommendations", []))
    report_path = synthesis_report["paths"].get("carbon_fiber_evidence_map_md")
    if report_path and Path(report_path).exists():
      st.subheader("Carbon Fiber Evidence Map v1")
      st.markdown(Path(report_path).read_text(encoding="utf-8"))
    st.write("保存先:", synthesis_report["paths"])

  if strategy:
    with st.expander("Full strategy JSON"):
      st.code(json.dumps(strategy, indent=2, ensure_ascii=False), language="json")


def main() -> None:
  render_search_strategy_page()


if __name__ == "__main__":
  main()
