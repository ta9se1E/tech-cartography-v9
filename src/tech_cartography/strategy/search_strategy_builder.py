"""Search strategy builder for Carbon Fiber Evidence Map."""

from __future__ import annotations

from typing import Any

from tech_cartography.config import load_search_strategy_defaults
from tech_cartography.domain.patent_record import PatentRecord
from tech_cartography.domain.search_profile import SearchProfile
from tech_cartography.strategy.query_plan import QueryPlan
from tech_cartography.strategy.seed_patent_analyzer import (
  DEFAULT_EXCLUDE_CANDIDATES,
  analyze_seed_patents,
)

CORE_CARBON_FIBER_TERMS = [
  "carbon fiber",
  "carbon fibre",
  "CFRP",
]

PAN_TERMS = [
  "PAN",
  "polyacrylonitrile",
  "precursor fiber",
]

SEARCH_INTENTS = [
  {
    "intent_id": "core_manufacturing",
    "label": "Core manufacturing",
    "description": "PAN系炭素繊維の製造・耐炎化・炭化・熱処理",
    "query_hint": "PAN AND carbon fiber AND carbonization",
  },
  {
    "intent_id": "surface_interface",
    "label": "Surface / interface",
    "description": "表面処理・sizing・界面接着",
    "query_hint": "carbon fiber AND surface treatment AND interface adhesion",
  },
  {
    "intent_id": "bundle_prepreg",
    "label": "Bundle / prepreg",
    "description": "炭素繊維束・tow・prepreg",
    "query_hint": "carbon fiber bundle OR tow OR prepreg",
  },
  {
    "intent_id": "application",
    "label": "Application",
    "description": "圧力容器・航空宇宙・自動車・複合材用途",
    "query_hint": "carbon fiber AND pressure vessel OR aerospace OR composite",
  },
  {
    "intent_id": "company_watch",
    "label": "Company watch",
    "description": "主要企業周辺の出願",
    "query_hint": "TORAY OR TEIJIN OR MITSUBISHI CHEMICAL AND carbon fiber",
  },
]

BROAD_RECALL_INTENT = {
  "intent_id": "broad_recall",
  "label": "Broad recall",
  "description": "テーマ語が広い場合の補助プラン",
  "query_hint": "carbon fiber OR CFRP OR polyacrylonitrile",
}


def _dedupe_terms(terms: list[str]) -> list[str]:
  seen: set[str] = set()
  deduped: list[str] = []
  for term in terms:
    normalized = term.strip()
    if not normalized:
      continue
    key = normalized.lower()
    if key in seen:
      continue
    seen.add(key)
    deduped.append(normalized)
  return deduped


def _merge_terms(*groups: list[str]) -> list[str]:
  merged: list[str] = []
  for group in groups:
    merged.extend(group)
  return _dedupe_terms(merged)


def _profile_summary(profile: SearchProfile) -> dict[str, Any]:
  terms = profile.normalized_terms()
  return {
    "theme": profile.theme,
    "search_goal": profile.search_goal,
    "materials": terms["materials"],
    "processes": terms["processes"],
    "properties": terms["properties"],
    "applications": terms["applications"],
    "companies": terms["companies"],
    "countries": terms["countries"],
    "year_min": profile.year_min,
    "year_max": profile.year_max,
    "max_results_total": profile.max_results_total,
    "max_results_per_intent": profile.max_results_per_intent,
  }


def _merged_exclude_terms(
  profile: SearchProfile,
  seed_analysis: dict[str, Any] | None,
  defaults: dict[str, Any],
) -> list[str]:
  return _merge_terms(
    list(defaults.get("default_exclude_terms", DEFAULT_EXCLUDE_CANDIDATES)),
    profile.exclude_terms,
    list((seed_analysis or {}).get("candidate_exclude_terms", [])),
  )


def _merged_companies(profile: SearchProfile, seed_analysis: dict[str, Any] | None) -> list[str]:
  defaults = load_search_strategy_defaults()
  return _merge_terms(
    profile.companies,
    list(defaults.get("default_companies", [])),
    list((seed_analysis or {}).get("companies", [])),
  )


def _is_theme_too_broad(profile: SearchProfile) -> bool:
  if len(profile.theme.split()) > 8:
    return True
  broad_markers = {"composite", "material", "fiber", "technology", "general"}
  theme_tokens = {token.lower() for token in profile.theme.replace("/", " ").split()}
  return len(theme_tokens & broad_markers) >= 2 and not profile.materials


def _detect_missing_inputs(
  profile: SearchProfile,
  seed_patents: list[PatentRecord] | None,
) -> list[str]:
  missing: list[str] = []
  if not profile.materials:
    missing.append("対象材料")
  if not profile.processes:
    missing.append("対象工程")
  if not profile.properties:
    missing.append("対象物性")
  if not profile.applications:
    missing.append("対象用途")
  if not profile.companies:
    missing.append("対象企業")
  if not profile.countries:
    missing.append("対象国")
  if profile.year_min is None and profile.year_max is None:
    missing.append("対象年")
  if not profile.exclude_terms:
    missing.append("除外領域")
  if not seed_patents:
    missing.append("類似特許の有無")
  return missing


def build_query_plans(
  profile: SearchProfile,
  seed_analysis: dict[str, Any] | None = None,
) -> list[QueryPlan]:
  """Build intent-specific query plans from profile and optional seed analysis."""
  defaults = load_search_strategy_defaults()
  seed_analysis = seed_analysis or {}

  exclude_terms = _merged_exclude_terms(profile, seed_analysis, defaults)
  companies = _merged_companies(profile, seed_analysis)
  seed_materials = list(seed_analysis.get("materials", []))
  seed_processes = list(seed_analysis.get("processes", []))
  seed_properties = list(seed_analysis.get("properties", []))
  seed_applications = list(seed_analysis.get("applications", []))

  materials = _merge_terms(profile.materials, PAN_TERMS, seed_materials)
  processes = _merge_terms(profile.processes, seed_processes)
  properties = _merge_terms(profile.properties, seed_properties)
  applications = _merge_terms(profile.applications, seed_applications)

  plans: list[QueryPlan] = [
    QueryPlan(
      intent_id="core_manufacturing",
      purpose="PAN系炭素繊維の製造・耐炎化・炭化・熱処理を拾う",
      query_hint="PAN AND carbon fiber AND carbonization",
      must_have_terms=_merge_terms(CORE_CARBON_FIBER_TERMS, ["PAN"]),
      should_have_terms=_merge_terms(
        materials,
        ["carbonization", "stabilization", "heat treatment"],
        processes,
        properties,
      ),
      exclude_terms=exclude_terms,
      target_companies=companies,
      target_countries=profile.countries,
      year_min=profile.year_min,
      year_max=profile.year_max,
      recommended_bigquery_mode="focused_lightweight",
      expected_noise_risk="Medium",
      max_results=profile.max_results_per_intent,
      notes=[
        "Focused carbon fiber process plan for PAN precursor route.",
        "Equivalent to focused_carbon_fiber_process in earlier versions.",
      ],
    ),
    QueryPlan(
      intent_id="surface_interface",
      purpose="表面処理・sizing・界面接着を拾う",
      query_hint="carbon fiber AND surface treatment AND interface adhesion",
      must_have_terms=_merge_terms(CORE_CARBON_FIBER_TERMS),
      should_have_terms=_merge_terms(
        ["surface treatment", "sizing", "interface adhesion"],
        processes,
        properties,
      ),
      exclude_terms=exclude_terms,
      target_companies=companies,
      target_countries=profile.countries,
      year_min=profile.year_min,
      year_max=profile.year_max,
      recommended_bigquery_mode="lightweight",
      expected_noise_risk="Medium",
      max_results=profile.max_results_per_intent,
      notes=["Surface and interface adhesion evidence map."],
    ),
    QueryPlan(
      intent_id="bundle_prepreg",
      purpose="炭素繊維束・tow・prepregを拾う",
      query_hint="carbon fiber bundle OR tow OR prepreg",
      must_have_terms=_merge_terms(CORE_CARBON_FIBER_TERMS),
      should_have_terms=_merge_terms(
        ["bundle", "tow", "prepreg"],
        applications,
        materials,
      ),
      exclude_terms=exclude_terms,
      target_companies=companies,
      target_countries=profile.countries,
      year_min=profile.year_min,
      year_max=profile.year_max,
      recommended_bigquery_mode="lightweight",
      expected_noise_risk="Medium",
      max_results=profile.max_results_per_intent,
      notes=["Intermediate product and prepreg route."],
    ),
    QueryPlan(
      intent_id="application",
      purpose="圧力容器・航空宇宙・自動車・複合材用途を拾う",
      query_hint="carbon fiber AND pressure vessel OR aerospace OR composite",
      must_have_terms=_merge_terms(CORE_CARBON_FIBER_TERMS),
      should_have_terms=_merge_terms(
        ["pressure vessel", "aerospace", "automotive", "composite"],
        applications,
      ),
      exclude_terms=exclude_terms,
      target_companies=companies,
      target_countries=profile.countries,
      year_min=profile.year_min,
      year_max=profile.year_max,
      recommended_bigquery_mode="lightweight",
      expected_noise_risk="High",
      max_results=profile.max_results_per_intent,
      notes=["Application-oriented evidence map."],
    ),
    QueryPlan(
      intent_id="company_watch",
      purpose="主要企業周辺の出願を拾う",
      query_hint="TORAY OR TEIJIN OR MITSUBISHI CHEMICAL AND carbon fiber",
      must_have_terms=_merge_terms(CORE_CARBON_FIBER_TERMS),
      should_have_terms=_merge_terms(companies, materials),
      exclude_terms=exclude_terms,
      target_companies=companies,
      target_countries=profile.countries,
      year_min=profile.year_min,
      year_max=profile.year_max,
      recommended_bigquery_mode="assignee_focused",
      expected_noise_risk="Low",
      max_results=profile.max_results_per_intent,
      notes=["Company watch for carbon fiber competitors."],
    ),
  ]

  if _is_theme_too_broad(profile) and not seed_analysis.get("seed_summary", {}).get(
    "seed_count",
  ):
    plans.append(
      QueryPlan(
        intent_id="broad_recall",
        purpose=BROAD_RECALL_INTENT["description"],
        query_hint=BROAD_RECALL_INTENT["query_hint"],
        must_have_terms=_merge_terms(CORE_CARBON_FIBER_TERMS),
        should_have_terms=_merge_terms(materials, processes, properties, applications),
        exclude_terms=exclude_terms,
        target_companies=companies,
        target_countries=profile.countries,
        year_min=profile.year_min,
        year_max=profile.year_max,
        recommended_bigquery_mode="lightweight",
        expected_noise_risk="High",
        max_results=profile.max_results_per_intent,
        notes=["Auxiliary broad recall plan when theme is broad and no seed patents exist."],
      ),
    )

  return plans


def choose_recommended_plan(query_plans: list[QueryPlan]) -> str:
  """Choose the first plan to run for carbon fiber evidence mapping."""
  intent_ids = {plan.intent_id for plan in query_plans}
  if "core_manufacturing" in intent_ids:
    return "core_manufacturing"
  if "focused_carbon_fiber_process" in intent_ids:
    return "focused_carbon_fiber_process"
  if "broad_recall" in intent_ids:
    return "broad_recall"
  return query_plans[0].intent_id if query_plans else ""


def validate_search_strategy(strategy: dict[str, Any]) -> dict[str, Any]:
  """Validate generated search strategy before BigQuery execution."""
  issues: list[str] = []
  warnings = list(strategy.get("warnings", []))

  query_plans = strategy.get("query_plans", [])
  if not query_plans:
    issues.append("query_plans is empty")

  required_intents = {
    "core_manufacturing",
    "surface_interface",
    "bundle_prepreg",
    "application",
    "company_watch",
  }
  present_intents = {plan.get("intent_id") for plan in query_plans}
  missing_intents = sorted(required_intents - present_intents)
  if missing_intents:
    issues.append(f"missing intents: {', '.join(missing_intents)}")

  for plan in query_plans:
    exclude_terms = [term.lower() for term in plan.get("exclude_terms", [])]
    if "pan" in exclude_terms:
      issues.append(f"{plan.get('intent_id')}: PAN must not be in exclude_terms")

  status = "ready" if not issues else "needs_review"
  return {
    "status": status,
    "issues": issues,
    "warnings": warnings,
    "recommended_first_plan": strategy.get("recommended_first_plan"),
  }


def build_search_strategy(
  profile: SearchProfile,
  seed_patents: list[PatentRecord] | None = None,
) -> dict[str, Any]:
  """Build a complete search strategy document."""
  seed_patents = seed_patents or []
  seed_analysis = analyze_seed_patents(seed_patents) if seed_patents else None
  query_plans = build_query_plans(profile, seed_analysis)
  recommended_first_plan = choose_recommended_plan(query_plans)

  warnings: list[str] = []
  if seed_analysis:
    warnings.extend(seed_analysis.get("warnings", []))
  if _is_theme_too_broad(profile) and not seed_patents:
    warnings.append(
      "Theme is broad and no seed patents were provided; broad_recall may be used as auxiliary.",
    )

  missing_user_inputs = _detect_missing_inputs(profile, seed_patents or None)
  next_actions = [
    "Review query plans and confirm intent priorities.",
    "Run BigQuery light multi-query retrieval in the next phase.",
    "Upload richer seed patents if evidence coverage is low.",
  ]
  if missing_user_inputs:
    next_actions.insert(0, "Fill missing user inputs before retrieval execution.")

  strategy = {
    "status": "draft",
    "profile_summary": _profile_summary(profile),
    "seed_patent_summary": seed_analysis.get("seed_summary") if seed_analysis else {
      "seed_count": 0,
      "coverage_level": "Low",
    },
    "search_intents": SEARCH_INTENTS,
    "query_plans": [plan.to_dict() for plan in query_plans],
    "recommended_first_plan": recommended_first_plan,
    "warnings": _dedupe_terms(warnings),
    "missing_user_inputs": missing_user_inputs,
    "next_actions": next_actions,
  }

  validation = validate_search_strategy(strategy)
  strategy["validation"] = validation
  strategy["status"] = validation["status"]
  return strategy
