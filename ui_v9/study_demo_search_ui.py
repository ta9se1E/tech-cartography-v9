"""Study demo temporary keyword search UI (Stage C1)."""

from __future__ import annotations

from typing import Any, Mapping

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

STATE_ACTIVE_CONTEXT = "v9_study_demo_active_context"
STATE_ACTIVE_CONTEXT_GENERATION = "v9_study_demo_active_context_generation"
STATE_ACTIVE_CONTEXT_MESSAGE = "v9_study_demo_active_context_message"
STATE_ACTIVE_CONTEXT_RUN_ID = "study_demo_active_context_run_id"

STATE_SELECTED_HISTORY_RUN_ID = "study_demo_selected_history_run_id"
STATE_SELECTED_HISTORY_LOADED = "study_demo_selected_history_loaded"
KEY_CONFIRM_ACTIVATE_RUN = "study_demo_confirm_activate_run"
KEY_ACTIVATE_RUN_BUTTON = "study_demo_activate_run_button"
KEY_RELOAD_ACTIVE_CONTEXT_BUTTON = "study_demo_reload_active_context_button"

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
  history_run_ids = [str(item.get("search_run_id", "")) for item in history if str(item.get("search_run_id", "")).strip()]
  selected = st.selectbox(
    "保存済み検索run",
    options=[""] + history_run_ids,
    format_func=lambda value: value or "選択してください",
    key=STATE_SELECTED_HISTORY_RUN_ID,
  )
  if selected:
    loaded = load_search_run(selected)
    st.session_state[STATE_SELECTED_HISTORY_LOADED] = loaded
    events.update(
      render_active_run_selector(
        selected_run_id=selected,
        loaded=loaded,
        authenticated=authenticated,
      )
    )
    history_result = build_search_result_from_artifacts(loaded)
    st.session_state[STATE_SEARCH_RESULT] = history_result
    events["history_loaded"] = history_result
    events["history_loaded_artifacts"] = loaded
    st.caption("履歴は保存済みartifactのみ再表示します（API呼び出しなし）。関連度はローカル再計算されます。")
    _render_search_result(history_result)
  elif history_run_ids:
    events.update(render_active_run_selector(selected_run_id="", loaded={}, authenticated=authenticated))
  return events


def render_active_run_selector(
  *,
  selected_run_id: str,
  loaded: Mapping[str, Any],
  authenticated: bool,
) -> dict[str, Any]:
  """Render active run selector immediately after history dropdown."""
  from services_v9.study_demo_active_run_selector import (
    format_save_result_message,
    resolve_activation_state,
    should_show_active_run_selector,
    summarize_run_for_selector,
  )
  from services_v9.study_demo_analysis_context import build_active_context_from_run, save_active_context_to_storage
  from services_v9.study_demo_config import get_study_demo_bucket

  events: dict[str, Any] = {}
  st.markdown("#### 分析対象として使用")
  if not authenticated:
    st.info("認証後に分析対象を設定できます。")
    return events

  active = dict(st.session_state.get(STATE_ACTIVE_CONTEXT, {}) or {})
  active_run_id = str(active.get("active_search_run_id", "") or st.session_state.get(STATE_ACTIVE_CONTEXT_RUN_ID, "") or "")

  history_run_ids = [str(item.get("search_run_id", "")) for item in list_search_history(limit=10) if item.get("search_run_id")]
  if not should_show_active_run_selector(
    authenticated=authenticated,
    history_run_ids=history_run_ids,
    selected_run_id=selected_run_id,
  ):
    st.info(
      "分析対象が未選択です。上の検索履歴から保存済みrunを選択し、"
      "このセクションで「この検索runを分析対象に設定」を押してください。"
    )
    if active_run_id:
      st.success(f"現在の分析対象: `{active_run_id}`")
    if st.button("現在の分析対象を再読み込み", key=KEY_RELOAD_ACTIVE_CONTEXT_BUTTON):
      events.update(_reload_active_context_from_storage())
      st.rerun()
    _render_active_context_message()
    return events

  artifacts = dict(loaded.get("artifacts", {}) or {})
  history_result = build_search_result_from_artifacts(loaded)
  summary = summarize_run_for_selector(
    search_run_id=selected_run_id,
    artifacts=artifacts,
    integrated=dict(history_result.get("integrated_signals", {}) or {}),
  )

  st.write(f"**選択中のrun:** `{summary['search_run_id']}`")
  if summary.get("theme"):
    st.write(f"**テーマ:** {str(summary['theme'])[:200]}")
  counts = dict(summary.get("provider_counts", {}) or {})
  tiers = dict(summary.get("tier_counts", {}) or {})
  st.write(
    f"**件数:** Patent {counts.get('patent', 0)} / Paper {counts.get('paper', 0)} / Web {counts.get('web', 0)}"
  )
  st.write(
    f"**Tier:** A {tiers.get('A', 0)} / B {tiers.get('B', 0)} / C {tiers.get('C', 0)} / D {tiers.get('D', 0)}"
  )
  st.caption("この設定は勉強会参加者全員に共有されます。外部APIや新規検索は実行しません。")

  is_current_active = active_run_id == selected_run_id
  if is_current_active:
    st.success(f"現在の分析対象: `{active_run_id}`")
  elif active_run_id:
    st.warning(f"現在の分析対象 `{active_run_id}` から `{selected_run_id}` へ切り替わります。")

  reload_clicked = st.button("現在の分析対象を再読み込み", key=KEY_RELOAD_ACTIVE_CONTEXT_BUTTON)
  confirm = False
  if not is_current_active:
    confirm = st.checkbox("このrunを参加者共通の分析対象に設定します", key=KEY_CONFIRM_ACTIVATE_RUN)
    activate_clicked = st.button("この検索runを分析対象に設定", key=KEY_ACTIVATE_RUN_BUTTON)
  else:
    activate_clicked = False

  decision = resolve_activation_state(
    selected_run_id=selected_run_id,
    active_run_id=active_run_id,
    confirm_checked=confirm,
    activate_clicked=activate_clicked,
    reload_clicked=reload_clicked,
    artifacts=artifacts,
  )

  if decision.get("action") == "reload":
    events.update(_reload_active_context_from_storage())
    st.rerun()

  if decision.get("action") == "error":
    st.error(str(decision.get("message", "分析対象を設定できません。")))

  if decision.get("action") == "idempotent":
    st.session_state[STATE_ACTIVE_CONTEXT_MESSAGE] = str(decision.get("message", ""))
    st.session_state[STATE_ACTIVE_CONTEXT_RUN_ID] = selected_run_id
    st.session_state["ui_data_source_mode"] = "temporary_search"

  if decision.get("action") == "save":
    preview = build_active_context_from_run(
      search_run_id=selected_run_id,
      artifacts=artifacts,
      bucket_name=get_study_demo_bucket(),
    )
    save_result = save_active_context_to_storage(
      preview,
      expected_generation=st.session_state.get(STATE_ACTIVE_CONTEXT_GENERATION),
    )
    status = str(save_result.get("status", "") or "")
    if status == "conflict":
      st.error(format_save_result_message(status=status, search_run_id=selected_run_id))
    elif status in {"saved", "unchanged"}:
      context = dict(save_result.get("context", preview))
      st.session_state[STATE_ACTIVE_CONTEXT] = context
      st.session_state[STATE_ACTIVE_CONTEXT_GENERATION] = save_result.get("generation")
      st.session_state[STATE_ACTIVE_CONTEXT_RUN_ID] = selected_run_id
      st.session_state[STATE_ACTIVE_CONTEXT_MESSAGE] = format_save_result_message(
        status=status,
        search_run_id=selected_run_id,
      )
      st.session_state["ui_data_source_mode"] = "temporary_search"
      events["active_context_set"] = context
      st.success(st.session_state[STATE_ACTIVE_CONTEXT_MESSAGE])
      st.rerun()
    else:
      detail = save_result.get("errors") or save_result.get("message") or "unknown"
      st.error(f"分析対象の保存に失敗しました。外部検索は実行されていません。 ({detail})")

  _render_active_context_message()
  return events


def _reload_active_context_from_storage() -> dict[str, Any]:
  from services_v9.study_demo_active_loader import load_active_analysis_context
  from services_v9.study_demo_analysis_context import save_active_context_to_storage
  from services_v9.study_demo_resolved_context import build_resolved_context_cache_patch, resolve_active_run_counts

  events: dict[str, Any] = {}
  loaded = load_active_analysis_context(reload_from_storage=True)
  if loaded.get("status") == "ok":
    context = dict(loaded.get("context", {}) or {})
    resolved = resolve_active_run_counts(context)
    patched = {**context, **build_resolved_context_cache_patch(resolved)}
    save_result = save_active_context_to_storage(
      patched,
      expected_generation=loaded.get("generation"),
    )
    if save_result.get("status") == "conflict":
      st.session_state[STATE_ACTIVE_CONTEXT_MESSAGE] = (
        "別の参加者が分析対象を更新しました。現在の分析対象を再読み込みしてください。"
      )
      return events
    context = dict(save_result.get("context", patched))
    st.session_state[STATE_ACTIVE_CONTEXT] = context
    st.session_state[STATE_ACTIVE_CONTEXT_GENERATION] = save_result.get("generation")
    st.session_state[STATE_ACTIVE_CONTEXT_RUN_ID] = str(context.get("active_search_run_id", "") or "")
    st.session_state[STATE_ACTIVE_CONTEXT_MESSAGE] = "分析対象を再読み込みしました。"
    st.session_state["ui_data_source_mode"] = "temporary_search"
    events["active_context_reloaded"] = context
    events["resolved_context"] = resolved
  else:
    st.session_state.pop(STATE_ACTIVE_CONTEXT, None)
    st.session_state.pop(STATE_ACTIVE_CONTEXT_GENERATION, None)
    st.session_state.pop(STATE_ACTIVE_CONTEXT_RUN_ID, None)
    st.session_state[STATE_ACTIVE_CONTEXT_MESSAGE] = "共有分析対象は未設定です。"
  return events


def _render_active_context_message() -> None:
  message = str(st.session_state.get(STATE_ACTIVE_CONTEXT_MESSAGE, "") or "")
  if message:
    st.caption(message)


def _render_active_run_controls(events: dict[str, Any]) -> None:
  """Deprecated: use render_active_run_selector()."""
  return None


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
  from ui_v9.study_demo_source_link import render_external_source_link

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
    render_external_source_link(
      signal,
      key_namespace="sources_integrated",
      search_run_id=str(signal.get("search_run_id", "") or ""),
      label="引用元を開く",
    )
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
  from ui_v9.study_demo_download_keys import build_study_demo_download_key

  run_id = str(result.get("search_run_id", "") or "")
  if export.get("integrated_csv"):
    st.download_button(
      "Integrated CSV (filtered)",
      data=export["integrated_csv"],
      file_name="integrated_filtered.csv",
      key=build_study_demo_download_key("information", "integrated_csv_filtered", run_id),
    )
  if export.get("integrated_csv_all_tiers"):
    st.download_button(
      "Integrated CSV (all tiers)",
      data=export["integrated_csv_all_tiers"],
      file_name="integrated_all.csv",
      key=build_study_demo_download_key("information", "integrated_csv_all_tiers", run_id),
    )
  if export.get("all_results_json"):
    st.download_button(
      "All Results JSON",
      data=export["all_results_json"],
      file_name="results_all.json",
      key=build_study_demo_download_key("information", "all_results_json", run_id),
    )
  if export.get("filtered_results_json"):
    st.download_button(
      "Filtered Results JSON",
      data=export["filtered_results_json"],
      file_name="results_filtered.json",
      key=build_study_demo_download_key("information", "filtered_results_json", run_id),
    )
  if export.get("integrated_markdown"):
    st.download_button(
      "Integrated Markdown (all)",
      data=export["integrated_markdown"],
      file_name="integrated_all.md",
      key=build_study_demo_download_key("information", "integrated_markdown_all", run_id),
    )
