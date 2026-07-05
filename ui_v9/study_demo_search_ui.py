"""Study demo temporary keyword search UI (Stage C1)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from services_v9.study_demo_config import is_study_demo_search_enabled
from services_v9.study_demo_search import (
  StudyDemoSearchRequest,
  build_search_plan_preview,
  execute_three_source_search,
  list_search_history,
  load_search_run,
  parse_search_request,
  validate_search_request,
)

STATE_SEARCH_FORM = "v9_study_demo_search_form"
STATE_SEARCH_PLAN = "v9_study_demo_search_plan"
STATE_SEARCH_RESULT = "v9_study_demo_search_result"
STATE_EXECUTED_PLAN_IDS = "v9_study_demo_executed_plan_ids"


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
        events["search_plan_created"] = plan
        st.success("検索計画を作成しました。本検索はまだ実行していません。")
    except ValueError as exc:
      st.error(str(exc))

  plan = dict(st.session_state.get(STATE_SEARCH_PLAN, {}) or {})
  if plan:
    st.markdown("#### 検索計画")
    st.json({k: plan.get(k) for k in ("search_plan_id", "summary", "cost_estimate", "providers")})
    confirmed = st.checkbox("計画と費用・API利用を確認した")
    if execute_button:
      if not confirmed:
        st.error("本検索前に確認チェックが必要です。")
      else:
        try:
          request = parse_search_request(payload)
          executed_ids = set(st.session_state.get(STATE_EXECUTED_PLAN_IDS, set()) or set())
          result = execute_three_source_search(
            request,
            plan=plan,
            confirmed=confirmed,
            executed_plan_ids=executed_ids,
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
    events["history_loaded"] = load_search_run(selected)
    st.caption("履歴は保存済みartifactのみ再表示します（API呼び出しなし）。")
    st.json({k: events["history_loaded"].get("artifacts", {}).get("search_status.json", {}) for k in [""]})

  return events


def _render_search_result(result: dict[str, Any]) -> None:
  st.markdown("#### 実行summary")
  st.write(f"- status: `{result.get('status')}`")
  st.write(f"- search_run_id: `{result.get('search_run_id')}`")
  provider_status = dict(result.get("provider_status", {}) or {})
  st.markdown("#### provider status")
  for name, item in provider_status.items():
    st.write(f"- {name}: `{dict(item).get('status')}`")
  integrated = dict(result.get("integrated_signals", {}) or {})
  st.markdown("#### Integrated Signals")
  st.write(f"- ranked_count: `{integrated.get('ranked_count', 0)}`")
  signals = list(integrated.get("signals", []) or [])[:20]
  for signal in signals:
    with st.expander(str(signal.get("title", ""))[:120]):
      st.write(signal.get("summary", ""))
  usage = dict(result.get("usage_metrics", {}) or {})
  st.markdown("#### Usage / Cost")
  st.json(usage)
  export = dict(result.get("export", {}) or {})
  if export.get("integrated_csv"):
    st.download_button("Integrated CSV", data=export["integrated_csv"], file_name="integrated.csv")
  if export.get("all_results_json"):
    st.download_button("All Results JSON", data=export["all_results_json"], file_name="results.json")
