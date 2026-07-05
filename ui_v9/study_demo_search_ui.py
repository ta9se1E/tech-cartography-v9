"""Study demo temporary keyword search UI (Stage C1)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from services_v9.study_demo_config import is_study_demo_search_enabled
from services_v9.study_demo_search import (
  build_search_plan_preview,
  execute_three_source_search,
  list_search_history,
  load_search_run,
  parse_search_request,
  validate_search_request,
)
from services_v9.study_demo_search.export import build_export_bundle as _build_export_bundle
from services_v9.study_demo_search.relevance_ranking import (
  TIER_A,
  TIER_B,
  TIER_C,
  TIER_D,
  filter_ranked_signals,
  group_signals_by_tier,
)
from services_v9.study_demo_search.request import request_fingerprint
from services_v9.study_demo_search.storage import build_search_result_from_artifacts

STATE_SEARCH_FORM = "v9_study_demo_search_form"
STATE_SEARCH_PLAN = "v9_study_demo_search_plan"
STATE_SEARCH_RESULT = "v9_study_demo_search_result"
STATE_EXECUTED_PLAN_IDS = "v9_study_demo_executed_plan_ids"
STATE_FILTER_KEY = "v9_study_demo_relevance_filters"


def _default_filters() -> dict[str, Any]:
  return {
    "show_tier_a": True,
    "show_tier_b": True,
    "show_tier_c": False,
    "show_tier_d": False,
    "min_score": 35,
    "source_patent": True,
    "source_paper": True,
    "source_web": True,
    "pan_only": False,
    "include_pitch": True,
    "include_background": True,
    "export_mode": "filtered",
  }


def _active_tiers(filters: dict[str, Any]) -> list[str]:
  tiers: list[str] = []
  if filters.get("show_tier_a", True):
    tiers.append(TIER_A)
  if filters.get("show_tier_b", True):
    tiers.append(TIER_B)
  if filters.get("show_tier_c", False):
    tiers.append(TIER_C)
  if filters.get("show_tier_d", False):
    tiers.append(TIER_D)
  return tiers


def _active_sources(filters: dict[str, Any]) -> list[str]:
  sources: list[str] = []
  if filters.get("source_patent", True):
    sources.append("patent")
  if filters.get("source_paper", True):
    sources.append("paper")
  if filters.get("source_web", True):
    sources.append("web_company")
  return sources


def _apply_filters(signals: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
  return filter_ranked_signals(
    signals,
    tiers=_active_tiers(filters),
    min_score=int(filters.get("min_score", 35) or 0),
    source_types=_active_sources(filters),
    pan_only=bool(filters.get("pan_only", False)),
    include_pitch=bool(filters.get("include_pitch", True)),
    include_background=bool(filters.get("include_background", True)),
  )


def render_study_demo_keyword_search_section(*, authenticated: bool = True) -> dict[str, Any]:
  events: dict[str, Any] = {}
  st.markdown("### 一時キーワード検索")
  if not authenticated:
    st.info("認証後に検索フォームが表示されます。")
    return events
  if not is_study_demo_search_enabled():
    st.warning("Study Demo の3情報源検索は現在停止中です。Stage C2 で有効化されます。")
    return events

  with st.form("v9_study_demo_search_form", clear_on_submit=False):
    theme = st.text_input("検索テーマ", max_chars=300)
    keywords_ja = st.text_input("日本語キーワード", max_chars=300)
    keywords_en = st.text_input("英語キーワード", max_chars=300)
    exact_phrase = st.text_input("完全一致フレーズ", max_chars=300)
    exclude_keywords = st.text_input("除外キーワード", max_chars=300)
    seed_patent = st.text_input("Seed特許番号（任意）", max_chars=300)
    year_cols = st.columns(2)
    year_start = year_cols[0].text_input("開始年", max_chars=4)
    year_end = year_cols[1].text_input("終了年", max_chars=4)
    provider_cols = st.columns(3)
    enable_patent = provider_cols[0].checkbox("Patent", value=True)
    enable_paper = provider_cols[1].checkbox("Paper", value=True)
    enable_web = provider_cols[2].checkbox("Web", value=True)
    plan_button = st.form_submit_button("検索計画を確認")
    execute_button = st.form_submit_button("3情報源を検索")

  payload = {
    "theme": theme,
    "keywords_ja": keywords_ja,
    "keywords_en": keywords_en,
    "exact_phrase": exact_phrase,
    "exclude_keywords": exclude_keywords,
    "seed_patent": seed_patent,
    "year_start": year_start,
    "year_end": year_end,
    "enable_patent": enable_patent,
    "enable_paper": enable_paper,
    "enable_web": enable_web,
  }

  if plan_button:
    try:
      request = parse_search_request(payload)
      errors = validate_search_request(request)
      if errors:
        st.error("; ".join(errors))
      else:
        plan = build_search_plan_preview(request)
        st.session_state[STATE_SEARCH_PLAN] = plan
        st.session_state.pop(STATE_SEARCH_RESULT, None)
        st.session_state.pop("v9_study_demo_search_confirmed", None)
        events["search_plan_created"] = plan
        st.success("検索計画を作成しました。本検索はまだ実行していません。")
    except ValueError as exc:
      st.error(str(exc))

  plan = dict(st.session_state.get(STATE_SEARCH_PLAN, {}) or {})
  if plan:
    try:
      current_request = parse_search_request(payload)
      current_fingerprint = request_fingerprint(current_request)
    except ValueError:
      current_fingerprint = ""
    if current_fingerprint and str(plan.get("request_fingerprint", "")) != current_fingerprint:
      st.warning("検索条件が変更されました。再度「検索計画を確認」を実行してください。")
      plan = {}
      st.session_state.pop(STATE_SEARCH_PLAN, None)
      st.session_state.pop("v9_study_demo_search_confirmed", None)
  if plan:
    st.markdown("#### 検索計画")
    st.json({k: plan.get(k) for k in ("search_plan_id", "summary", "cost_estimate", "providers")})
    try:
      current_request = parse_search_request(payload)
    except ValueError as exc:
      st.error(str(exc))
      current_request = None
    confirmed = st.checkbox("計画と費用・API利用を確認した", key="v9_study_demo_search_confirmed")
    patent_plan = dict(dict(plan.get("providers", {}) or {}).get("patent", {}) or {})
    patent_enabled = bool(current_request.enable_patent) if current_request else bool(plan.get("summary", {}).get("providers", {}).get("patent"))
    patent_blocks_execute = patent_plan.get("status") in {"dry_run_failed", "dry_run_zero_bytes"} or (
      patent_enabled and not bool(patent_plan.get("bigquery_execution_allowed", True))
    )
    if patent_blocks_execute and patent_enabled:
      st.error("Patent BigQuery dry-run が成功していないか、本実行が許可されていません。検索計画を再作成してください。")
    if execute_button:
      if patent_blocks_execute and patent_enabled:
        st.error("Patent dry-run 未完了のため本検索できません。")
      elif not confirmed:
        st.error("本検索前に確認チェックが必要です。")
      elif current_request is None:
        pass
      else:
        try:
          request = current_request
          executed_ids = set(st.session_state.get(STATE_EXECUTED_PLAN_IDS, set()) or set())
          result = execute_three_source_search(
            request,
            plan=plan,
            confirmed=confirmed,
            executed_plan_ids=execut_ids,
          )
          st.session_state[STATE_SEARCH_RESULT] = result
          if plan.get("search_plan_id"):
            executed_ids.add(str(plan["search_plan_id"]))
            st.session_state[STATE_EXECUTED_PLAN_IDS] = executed_ids
          events["search_executed"] = result
          st.success(f"検索完了: {result.get('status')}")
        except ValueError as exc:
          st.error(str(exc))

  result = dict(st.session_state.get(STATE_SEARCH_RESULT, {}) or {})
  if result:
    _render_search_result(result)

  st.markdown("#### 検索履歴")
  history = list_search_history(limit=10)
  selected = st.selectbox(
    "保存済み検索run",
    options=[""] + [str(item.get("search_run_id", "")) for item in history],
    format_func=lambda value: value or "選択してください",
  )
  if selected:
    loaded = load_search_run(selected)
    history_result = build_search_result_from_artifacts(loaded)
    st.session_state[STATE_SEARCH_RESULT] = history_result
    events["history_loaded"] = history_result
    st.caption("履歴は保存済みartifactのみ再表示します（API呼び出しなし）。関連度はローカル再計算されます。")
    _render_search_result(history_result)

  return events


def _render_filter_controls() -> dict[str, Any]:
  filters = dict(st.session_state.get(STATE_FILTER_KEY, _default_filters()) or _default_filters())
  st.markdown("#### 関連度フィルタ")
  cols = st.columns(4)
  filters["show_tier_a"] = cols[0].checkbox("Tier A 直接関連", value=filters.get("show_tier_a", True))
  filters["show_tier_b"] = cols[1].checkbox("Tier B 補助証拠", value=filters.get("show_tier_b", True))
  filters["show_tier_c"] = cols[2].checkbox("Tier C 背景資料", value=filters.get("show_tier_c", False))
  filters["show_tier_d"] = cols[3].checkbox("Tier D 低関連", value=filters.get("show_tier_d", False))
  cols2 = st.columns(4)
  filters["min_score"] = cols2[0].slider("minimum relevance score", 0, 100, int(filters.get("min_score", 35)))
  filters["source_patent"] = cols2[1].checkbox("Patent", value=filters.get("source_patent", True))
  filters["source_paper"] = cols2[2].checkbox("Paper", value=filters.get("source_paper", True))
  filters["source_web"] = cols2[3].checkbox("Web", value=filters.get("source_web", True))
  cols3 = st.columns(3)
  filters["pan_only"] = cols3[0].checkbox("PAN系のみ", value=filters.get("pan_only", False))
  filters["include_pitch"] = cols3[1].checkbox("ピッチ系を含める", value=filters.get("include_pitch", True))
  filters["include_background"] = cols3[2].checkbox("背景資料を含める", value=filters.get("include_background", True))
  filters["export_mode"] = st.radio(
    "Export対象",
    options=["filtered", "all"],
    format_func=lambda value: "表示対象のみ" if value == "filtered" else "全件（全Tier）",
    horizontal=True,
    index=0 if filters.get("export_mode", "filtered") == "filtered" else 1,
  )
  st.session_state[STATE_FILTER_KEY] = filters
  return filters


def _render_signal_card(signal: dict[str, Any]) -> None:
  title = str(signal.get("title", "") or "")[:140]
  tier = signal.get("relevance_tier", "")
  score = signal.get("relevance_score", "")
  with st.expander(f"[Tier {tier} | score {score}] {title}"):
    st.write(f"**関連度区分:** Tier {tier}")
    st.write(f"**relevance score:** {score}")
    st.write(f"**なぜ関連したか:** {signal.get('relevance_reason', '')}")
    st.write(f"**source type:** `{signal.get('source_type', '')}`")
    st.write(f"**organization:** {signal.get('organization', '')}")
    st.write(f"**publication date:** {signal.get('published_at', '')}")
    st.write(f"**URL:** {signal.get('url', '')}")
    st.write(f"**matched core terms:** {signal.get('matched_core_terms', [])}")
    st.write(f"**matched material terms:** {signal.get('matched_material_terms', [])}")
    st.write(f"**matched process/property terms:** {signal.get('matched_process_terms', [])} / {signal.get('matched_property_terms', [])}")
    st.write(f"**matched negative terms:** {signal.get('matched_negative_terms', [])}")
    st.write(f"**target material match:** {signal.get('target_material_match', '') or '-'}")
    st.write(f"**target material mismatch:** {signal.get('target_material_mismatch', '') or '-'}")
    st.write(f"**score breakdown:** {signal.get('score_breakdown', {})}")
    st.write(signal.get("summary", ""))


def _render_tier_section(title: str, signals: list[dict[str, Any]], *, max_items: int, collapsed: bool = False) -> None:
  st.markdown(f"#### {title} ({len(signals)}件)")
  if not signals:
    st.caption("該当なし")
    return
  container = st.expander(title, expanded=not collapsed) if collapsed else st.container()
  with container:
    for signal in signals[:max_items]:
      _render_signal_card(signal)
    if len(signals) > max_items:
      st.caption(f"表示上限 {max_items} 件。残り {len(signals) - max_items} 件はExportで確認できます。")


def _render_search_result(result: dict[str, Any]) -> None:
  st.markdown("#### 実行summary")
  st.write(f"- status: `{result.get('status')}`")
  st.write(f"- search_run_id: `{result.get('search_run_id')}`")
  provider_status = dict(result.get("provider_status", {}) or {})
  st.markdown("#### provider status")
  for name, item in provider_status.items():
    st.write(f"- {name}: `{dict(item).get('status')}`")

  integrated = dict(result.get("integrated_signals", {}) or {})
  all_signals = list(integrated.get("signals", []) or [])
  summary = dict(integrated.get("relevance_summary", {}) or {})
  st.markdown("#### Integrated Signals")
  st.write(
    f"- ranked_count: `{integrated.get('ranked_count', len(all_signals))}` | "
    f"Tier A: `{summary.get('tier_a', 0)}` | Tier B: `{summary.get('tier_b', 0)}` | "
    f"Tier C: `{summary.get('tier_c', 0)}` | Tier D: `{summary.get('tier_d', 0)}`"
  )

  filters = _render_filter_controls()
  filtered = _apply_filters(all_signals, filters)
  grouped_all = group_signals_by_tier(all_signals)
  grouped_filtered = group_signals_by_tier(filtered)

  st.caption(f"フィルタ後: {len(filtered)} / {len(all_signals)} 件")

  tier_a = grouped_filtered[TIER_A] if filters.get("show_tier_a", True) else []
  tier_b = grouped_filtered[TIER_B] if filters.get("show_tier_b", True) else []
  tier_c = grouped_all[TIER_C] if filters.get("include_background", True) else []
  tier_d = grouped_filtered[TIER_D] if filters.get("show_tier_d", False) else []

  _render_tier_section("直接関連 (Tier A)", tier_a, max_items=30)
  _render_tier_section("補助的な証拠 (Tier B)", tier_b, max_items=30)
  _render_tier_section(
    "背景資料 (Tier C)",
    tier_c,
    max_items=30,
    collapsed=not filters.get("show_tier_c", False),
  )
  if filters.get("show_tier_d", False):
    _render_tier_section("低関連・除外候補 (Tier D)", tier_d, max_items=30)

  usage = dict(result.get("usage_metrics", {}) or {})
  st.markdown("#### Usage / Cost")
  st.json(usage)

  keywords = dict(result.get("keyword_suggestions", {}) or {})
  similar = dict(result.get("similar_patents", {}) or {})
  export_signals = filtered if filters.get("export_mode", "filtered") == "filtered" else all_signals
  export = _build_export_bundle(all_signals, keywords, similar, usage, filtered_signals=export_signals)
  if export.get("integrated_csv"):
    st.download_button("Integrated CSV (filtered)", data=export["integrated_csv"], file_name="integrated_filtered.csv")
  if export.get("integrated_csv_all_tiers"):
    st.download_button("Integrated CSV (all tiers)", data=export["integrated_csv_all_tiers"], file_name="integrated_all.csv")
  if export.get("all_results_json"):
    st.download_button("All Results JSON", data=export["all_results_json"], file_name="results_all.json")
  if export.get("filtered_results_json"):
    st.download_button("Filtered Results JSON", data=export["filtered_results_json"], file_name="results_filtered.json")
  if export.get("integrated_markdown"):
    st.download_button("Integrated Markdown (all)", data=export["integrated_markdown"], file_name="integrated_all.md")
