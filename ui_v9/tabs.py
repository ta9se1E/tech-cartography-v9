"""Tab renderers for the lightweight Tech Cartography v9 UI."""

from __future__ import annotations

from typing import Any, Sequence

import streamlit as st

from services_v9.signal_models import Signal, WatchProfile
from services_v9.review_state import (
  apply_reviews_to_signals,
  default_review_state,
  normalize_review_state,
  sort_signals_by_review,
  summarize_reviews,
)
from services_v9.signal_scoring import (
  build_diversity_counts,
  format_score_delta,
  select_diverse_top_signals,
  select_top_reads,
  summarize_status_buckets,
)
from ui_v9.labels import (
  FORBIDDEN_UI_LABELS,
  V9_TAB_LABELS,
  action_label_ja,
  bool_label_ja,
  cadence_label_ja,
  data_source_mode_label_ja,
  REVIEW_COMMENT_LABEL_JA,
  review_priority_label_ja,
  review_priority_value_ja,
  score_level_label_ja,
  source_mode_label_ja,
  status_label_ja,
  type_label_ja,
  watch_profile_suggestion_label_ja,
)

NOTICE_JA = (
  "v9は軽量なR&Dシグナル監視プレビューです。"
  "PDF/OCR深掘り、クレーム解釈、法的判断、FTO判断、侵害判断、"
  "特許性判断、技術的妥当性の証明は行いません。"
)

REVIEW_COMMENT_FIELD = "review" + "_comment"


def render_notice() -> None:
  st.info(NOTICE_JA)


def _show_status_message(message: str | None, kind: str = "success") -> None:
  if not message:
    return
  if kind == "warning":
    st.warning(message)
  elif kind == "error":
    st.error(message)
  else:
    st.success(message)


def _render_profile_summary(summary: dict[str, object]) -> None:
  counts = dict(summary.get("counts", {}))
  st.markdown("### 入力サマリー")
  st.write(f"- コアキーワード: 英語 {counts.get('core_en', 0)}件 / 日本語 {counts.get('core_ja', 0)}件")
  st.write(
    f"- 用途キーワード: 英語 {counts.get('application_en', 0)}件 / 日本語 {counts.get('application_ja', 0)}件"
  )
  st.write(
    f"- 材料・プロセスキーワード: 英語 {counts.get('material_process_en', 0)}件 / "
    f"日本語 {counts.get('material_process_ja', 0)}件"
  )
  st.write(f"- 除外キーワード: 英語 {counts.get('exclude_en', 0)}件 / 日本語 {counts.get('exclude_ja', 0)}件")
  st.write(f"- Seed公報: {counts.get('seed_publications', 0)}件")
  st.write(f"- 追加候補公報: {counts.get('candidate_publications', 0)}件")


def _search_country_enabled_key(country_code: str) -> str:
  return f"ui_search_country_enabled_{country_code}"


def _search_country_priority_key(country_code: str) -> str:
  return f"ui_search_country_priority_{country_code}"


def _search_country_official_key(country_code: str) -> str:
  return f"ui_search_country_official_{country_code}"


def _search_country_fallback_key(country_code: str) -> str:
  return f"ui_search_country_fallback_{country_code}"


def _search_intent_enabled_key(intent: str) -> str:
  return f"ui_search_intent_enabled_{intent}"


def _weekday_label_ja(value: str) -> str:
  labels = {
    "MON": "月曜日",
    "TUE": "火曜日",
    "WED": "水曜日",
    "THU": "木曜日",
    "FRI": "金曜日",
    "SAT": "土曜日",
    "SUN": "日曜日",
  }
  return labels.get(str(value or "").strip().upper(), str(value or "").strip().upper())


def _render_search_plan_validation(errors: list[str]) -> None:
  st.markdown("### validation結果")
  if not errors:
    st.success("validation passed")
    return
  for error in errors:
    st.warning(str(error))


def _render_search_plan_provider_routing(rows: list[dict[str, object]]) -> None:
  st.markdown("### Provider routing")
  for row in rows:
    st.write(
      f"- {row.get('country_region_code', 'n/a')}: "
      f"primary=`{row.get('provider_primary', '')}` / "
      f"fallback=`{row.get('provider_fallback', '') or 'なし'}` / "
      f"verification=`{row.get('verification_provider', '')}`"
    )


def _render_country_coverage(coverage_rows: list[dict[str, object]]) -> None:
  st.markdown("### 国・地域coverage")
  for row in coverage_rows:
    st.write(
      f"- {row.get('country_region_code', 'n/a')} {row.get('country_region_name_ja', '')} | "
      f"enabled: {bool_label_ja(bool(row.get('enabled', True)))} | "
      f"priority: {row.get('priority', 0)} | "
      f"query: {row.get('query_count', 0)}件 | "
      f"enabled query: {row.get('enabled_query_count', 0)}件"
    )


def _render_generated_queries(source_key: str, queries: list[dict[str, object]]) -> None:
  st.write("**自動生成query**")
  if not queries:
    st.caption("自動生成queryはありません。")
    return
  for query in queries:
    if source_key == "global_web":
      st.write(
        f"- `{query.get('query_id', '')}` | origin=`{query.get('origin', 'generated')}` | "
        f"{query.get('country_region_code', '')} / {query.get('web_intent', '')} / "
        f"{query.get('result_bucket', '')} / {query.get('priority', '')} / {query.get('query_local', '')}"
      )
    else:
      st.write(
        f"- `{query.get('query_id', '')}` | origin=`{query.get('origin', 'generated')}` | "
        f"{query.get('strategy', '')} / {query.get('language', '')} / {query.get('query_text', '')}"
      )


def _render_manual_queries(source_key: str, queries: list[dict[str, object]]) -> list[str]:
  delete_query_ids: list[str] = []
  st.write("**手動query**")
  if not queries:
    st.caption("手動queryはまだありません。")
    return delete_query_ids
  for query in queries:
    query_id = str(query.get("query_id", "") or "")
    columns = st.columns([6, 1])
    with columns[0]:
      if source_key == "global_web":
        st.write(
          f"- `{query_id}` | origin=`manual` | {query.get('country_region_code', '')} / "
          f"{query.get('web_intent', '')} / {query.get('result_bucket', '')} / {query.get('query_local', '')}"
        )
      else:
        st.write(
          f"- `{query_id}` | origin=`manual` | {query.get('strategy', '')} / "
          f"{query.get('language', '')} / {query.get('query_text', '')}"
        )
    with columns[1]:
      if st.button("削除", key=f"delete_manual_query_{query_id}", width="stretch"):
        delete_query_ids.append(query_id)
  return delete_query_ids


def _render_source_plan_expander(
  label: str,
  source_key: str,
  source_plan: dict[str, Any],
  manual_queries: list[dict[str, object]],
) -> list[str]:
  delete_query_ids: list[str] = []
  with st.expander(label, expanded=False):
    st.caption(f"最大件数: {source_plan.get('limit', 0)}件")
    notes = list(source_plan.get("notes", []) or [])
    for note in notes:
      st.write(f"- {note}")
    _render_generated_queries(source_key, list(source_plan.get("queries", []) or []))
    delete_query_ids.extend(_render_manual_queries(source_key, manual_queries))
  return delete_query_ids


def _render_patent_bigquery_preview(
  patent_bigquery_state: dict[str, Any],
  patent_bigquery_status_message: str | None = None,
  patent_retrieval_status_message: str | None = None,
) -> dict[str, bool]:
  preview = dict(patent_bigquery_state.get("preview", {}) or {})
  request = dict(preview.get("request", {}) or {})
  parameters = list(preview.get("parameters", []) or [])
  validation_rows = list(preview.get("validation_rows", []) or [])
  dry_run_result = dict(patent_bigquery_state.get("dry_run_result", {}) or {})
  retrieval_result = dict(patent_bigquery_state.get("retrieval_result", {}) or {})
  approved = bool(patent_bigquery_state.get("approved", False))

  st.markdown("### Patent BigQuery SQL Preview")
  _show_status_message(patent_bigquery_status_message)
  _show_status_message(patent_retrieval_status_message)
  st.caption("dry-run は明示ボタン時だけ実行します。ページ表示や Streamlit rerun だけでは BigQuery は呼びません。")
  if not request:
    st.warning("特許検索計画が未生成のため、SQL Preview を作成できません。")
    return {"run_patent_dry_run": False, "approve_patent_query": False, "run_patent_retrieval": False}

  query_options = list(preview.get("query_options", []) or [])
  if query_options:
    st.selectbox("特許query_id", options=query_options, key="ui_patent_bigquery_query_id")
  st.number_input("特許dry-run max results", min_value=1, max_value=1000, step=10, key="ui_patent_bigquery_max_results")

  st.write(f"- query_id: `{request.get('query_id', '')}`")
  st.write(f"- strategy: `{request.get('strategy', '')}` / language: `{request.get('language', '')}`")
  st.write(f"- publication window: `{request.get('publication_date_from', 0)}` - `{request.get('publication_date_to', 0)}`")
  st.write(f"- maximum_bytes_billed: `{request.get('maximum_bytes_billed', 0)}`")
  st.write(f"- 実行禁止フラグ: `{bool_label_ja(not bool(request.get('execute_enabled', False)))}`")
  st.write(f"- 承認状態: `{'承認済み' if approved else '未承認'}`")

  with st.expander("parameter preview", expanded=False):
    st.json(parameters)
  with st.expander("SQL Preview", expanded=False):
    st.code(str(preview.get("sql", "") or ""), language="sql")

  st.write("**query validation**")
  for row in validation_rows:
    status = str(row.get("status", "") or "")
    message = str(row.get("message", "") or "")
    if status == "error":
      st.error(message)
    elif status == "warning":
      st.warning(message)
    else:
      st.success(message)

  if dry_run_result:
    st.write("**最新 dry-run 結果**")
    dry_cols = st.columns(4)
    dry_cols[0].metric("estimated bytes", f"{int(dry_run_result.get('estimated_bytes', 0) or 0)}")
    dry_cols[1].metric("estimated GB", f"{float(dry_run_result.get('estimated_gb', 0.0) or 0.0):.4f}")
    dry_cols[2].metric("estimated cost", f"${float(dry_run_result.get('estimated_cost_usd', 0.0) or 0.0):.6f}")
    dry_cols[3].metric(
      "max bytes exceeded",
      bool_label_ja(bool(dry_run_result.get("would_be_blocked_by_max_bytes", False))),
    )
    if dry_run_result.get("error"):
      st.warning(str(dry_run_result.get("error")))

  if retrieval_result:
    st.write("**最新取得結果**")
    st.write(f"- provider status: `{retrieval_result.get('provider_status', '')}`")
    st.write(f"- retrieval_run_id: `{retrieval_result.get('retrieval_run_id', '')}`")
    st.write(f"- BigQuery job ID: `{retrieval_result.get('bigquery_job_id', '') or 'なし'}`")
    st.write(f"- staged rows: `{retrieval_result.get('rows_retrieved', 0)}`")
    if retrieval_result.get("error"):
      st.warning(str(retrieval_result.get("error")))

  button_left, button_mid, button_right = st.columns(3)
  with button_left:
    run_patent_dry_run = st.button("特許BigQuery dry-runを実行", key="btn_patent_bigquery_dry_run", width="stretch")
  with button_mid:
    approve_patent_query = st.button("このqueryを承認", key="btn_patent_bigquery_approve", width="stretch")
  with button_right:
    run_patent_retrieval = st.button("承認済み特許取得を実行", key="btn_patent_bigquery_execute", width="stretch")

  return {
    "run_patent_dry_run": run_patent_dry_run,
    "approve_patent_query": approve_patent_query,
    "run_patent_retrieval": run_patent_retrieval,
  }


def _render_paper_openalex_preview(
  paper_openalex_state: dict[str, Any],
  paper_retrieval_status_message: str | None = None,
) -> bool:
  preview = dict(paper_openalex_state.get("preview", {}) or {})
  request = dict(preview.get("request", {}) or {})
  validation_rows = list(preview.get("validation_rows", []) or [])
  retrieval_result = dict(paper_openalex_state.get("retrieval_result", {}) or {})

  st.markdown("### OpenAlex Paper Retrieval")
  _show_status_message(paper_retrieval_status_message)
  st.caption("OpenAlex 検索は明示ボタン時だけ実行します。Google Scholar 非公式スクレイピングは行いません。")
  if not request:
    st.warning("論文検索計画が未生成のため、OpenAlex query preview を作成できません。")
    return False

  query_options = list(preview.get("query_options", []) or [])
  if query_options:
    st.selectbox("論文query_id", options=query_options, key="ui_paper_openalex_query_id")
  st.number_input("OpenAlex max results", min_value=1, max_value=200, step=5, key="ui_paper_openalex_max_results")
  st.write(f"- query_id: `{request.get('query_id', '')}`")
  st.write(f"- strategy: `{request.get('strategy', '')}` / language: `{request.get('language', '')}`")
  st.write(f"- provider: `OpenAlex` / fallback interface: `Semantic Scholar future only`")
  st.write(f"- cursor paging: `ON` / per-page: `{request.get('per_page', 25)}` / retry_limit: `{request.get('retry_limit', 0)}`")

  with st.expander("OpenAlex URL Preview", expanded=False):
    st.code(str(preview.get("url_preview", "") or ""), language="text")

  st.write("**query validation**")
  for row in validation_rows:
    status = str(row.get("status", "") or "")
    message = str(row.get("message", "") or "")
    if status == "error":
      st.error(message)
    elif status == "warning":
      st.warning(message)
    else:
      st.success(message)

  if retrieval_result:
    st.write("**最新 retrieval 結果**")
    st.write(f"- provider status: `{retrieval_result.get('provider_status', '')}`")
    st.write(f"- retrieval_run_id: `{retrieval_result.get('retrieval_run_id', '')}`")
    st.write(f"- pages fetched: `{retrieval_result.get('pages_fetched', 0)}`")
    st.write(f"- staged rows: `{retrieval_result.get('rows_retrieved', 0)}`")
    if retrieval_result.get("error"):
      st.warning(str(retrieval_result.get("error")))

  return st.button("OpenAlex論文取得を実行", key="btn_openalex_paper_retrieval", width="stretch")


def _render_global_web_retrieval_preview(
  global_web_retrieval_state: dict[str, Any],
  global_web_retrieval_status_message: str | None = None,
) -> bool:
  preview = dict(global_web_retrieval_state.get("preview", {}) or {})
  request = dict(preview.get("request", {}) or {})
  validation_rows = list(preview.get("validation_rows", []) or [])
  retrieval_result = dict(global_web_retrieval_state.get("retrieval_result", {}) or {})

  st.markdown("### Global Web / Company Retrieval")
  _show_status_message(global_web_retrieval_status_message)
  st.caption("Global Web 検索は明示ボタン時だけ実行します。Discovery は Tavily、Verification fallback は Google Search Grounding を想定します。")
  if not request:
    st.warning("Global Web retrieval preview を作成できません。")
    return False

  input_cols = st.columns(3)
  with input_cols[0]:
    st.number_input("Global Web実行query上限", min_value=1, max_value=100, step=1, key="ui_global_web_max_queries")
  with input_cols[1]:
    st.number_input("Verification対象上限", min_value=1, max_value=50, step=1, key="ui_global_web_verification_limit")
  with input_cols[2]:
    st.number_input("日本語要約上位件数", min_value=1, max_value=50, step=1, key="ui_global_web_summary_top_n")

  st.write(f"- selected query数: `{preview.get('query_count', 0)}`")
  st.write(f"- verification limit: `{request.get('verification_limit', 0)}`")
  st.write(f"- summary top n: `{request.get('summary_top_n', 0)}`")
  st.write(f"- provider: `Tavily` / fallback: `Google Search Grounding`")

  with st.expander("Global Web execute preview", expanded=False):
    st.json({
      "selected_query_ids": preview.get("selected_query_ids", []),
      "verification_limit": request.get("verification_limit", 0),
      "summary_top_n": request.get("summary_top_n", 0),
    })

  st.write("**query validation**")
  for row in validation_rows:
    status = str(row.get("status", "") or "")
    message = str(row.get("message", "") or "")
    if status == "error":
      st.error(message)
    elif status == "warning":
      st.warning(message)
    else:
      st.success(message)

  if retrieval_result:
    st.write("**最新 retrieval 結果**")
    st.write(f"- provider status: `{retrieval_result.get('provider_status', '')}`")
    st.write(f"- retrieval_run_id: `{retrieval_result.get('retrieval_run_id', '')}`")
    st.write(f"- query count: `{retrieval_result.get('query_count', 0)}`")
    st.write(f"- staged rows: `{retrieval_result.get('rows_retrieved', 0)}`")
    if retrieval_result.get("error"):
      st.warning(str(retrieval_result.get("error")))

  return st.button("Global Web / 企業情報取得を実行", key="btn_global_web_retrieval", width="stretch")


def _signal_lookup_key(signal: Signal | dict[str, Any]) -> str:
  if isinstance(signal, Signal):
    signal_id = str(signal.id or "").strip()
    if signal_id:
      return f"id:{signal_id}"
    return f"title:{signal.title}|type:{signal.type}|date:{signal.published_date}"

  raw = signal or {}
  signal_id = str(raw.get("id", "") or "").strip()
  if signal_id:
    return f"id:{signal_id}"
  return (
    f"title:{str(raw.get('title', '') or '').strip()}|"
    f"type:{str(raw.get('type', '') or '').strip()}|"
    f"date:{str(raw.get('published_date', '') or '').strip()}"
  )


def _build_score_explanation_lookup(display_signals: Sequence[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
  lookup: dict[str, dict[str, Any]] = {}
  for signal in display_signals or []:
    lookup[_signal_lookup_key(signal)] = dict(signal.get("score_explanation", {}) or {})
  return lookup


def _build_display_signal_lookup(display_signals: Sequence[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
  lookup: dict[str, dict[str, Any]] = {}
  for signal in display_signals or []:
    lookup[_signal_lookup_key(signal)] = dict(signal)
  return lookup


def _merge_keyword_hits(
  matched_keywords: dict[str, Any] | None,
  keys: list[str],
) -> list[str]:
  if not isinstance(matched_keywords, dict):
    return []

  merged: list[str] = []
  seen: set[str] = set()
  for key in keys:
    values = matched_keywords.get(key, [])
    if not isinstance(values, list):
      continue
    for value in values:
      normalized = str(value or "").strip()
      if not normalized:
        continue
      dedupe_key = normalized.lower()
      if dedupe_key in seen:
        continue
      seen.add(dedupe_key)
      merged.append(normalized)
  return merged


def _render_keyword_hits(
  title: str,
  values: list[str],
  empty_text: str = "一致なし",
) -> None:
  st.write(f"**{title}**")
  if values:
    st.write(", ".join(values))
  else:
    st.caption(empty_text)


def _render_reason_list(
  title: str,
  values: list[str],
  empty_text: str | None = None,
) -> None:
  if not values and empty_text is None:
    return
  st.write(f"**{title}**")
  if values:
    for value in values:
      st.write(f"- {value}")
  elif empty_text is not None:
    st.caption(empty_text)


def _render_score_explanation(explanation: dict[str, Any] | None) -> None:
  payload = explanation or {}
  matched_keywords = dict(payload.get("matched_keywords", {}) or {})
  exclude_hits = dict(payload.get("exclude_hits", {}) or {})
  core_hits = _merge_keyword_hits(matched_keywords, ["core_en", "core_ja"])
  application_hits = _merge_keyword_hits(matched_keywords, ["application_en", "application_ja"])
  material_process_hits = _merge_keyword_hits(matched_keywords, ["material_process_en", "material_process_ja"])
  company_hits = _merge_keyword_hits(matched_keywords, ["target_companies"])
  exclude_values = _merge_keyword_hits(exclude_hits, ["exclude_en", "exclude_ja"])
  score = float(payload.get("score", 0.0) or 0.0)
  score_level = score_level_label_ja(str(payload.get("score_level", "") or ""))

  metric_left, metric_right = st.columns(2)
  metric_left.metric("スコア", f"{score:.2f}")
  metric_right.metric("関連度", score_level or "未設定")

  _render_keyword_hits("一致したコアキーワード", core_hits)
  _render_keyword_hits("一致した用途キーワード", application_hits)
  _render_keyword_hits("一致した材料・プロセスキーワード", material_process_hits)
  _render_keyword_hits("一致した注目企業", company_hits)

  st.write("**除外キーワード一致**")
  if exclude_values:
    st.warning("除外キーワード一致: " + ", ".join(exclude_values))
  else:
    st.caption("なし")

  _render_reason_list("スコアの主な理由", list(payload.get("score_reasons", []) or []), "明確な加点理由はありません。")
  _render_reason_list("注意点", list(payload.get("negative_reasons", []) or []))

  st.write("**システム判断の理由**")
  st.write(str(payload.get("action_reason", "") or "説明はまだありません。"))


def _get_review_for_signal(
  signal: dict[str, Any],
  signal_id: str,
  reviews_by_signal_id: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
  reviews = reviews_by_signal_id or {}
  if signal_id in reviews:
    return normalize_review_state(reviews[signal_id])
  if isinstance(signal.get("review"), dict):
    return normalize_review_state(signal.get("review"))
  return default_review_state(signal)


def _ensure_review_widget_defaults(signal_id: str, review: dict[str, Any]) -> tuple[str, str, str, str]:
  decision_key = f"review_decision_{signal_id}"
  priority_key = f"review_priority_{signal_id}"
  comment_key = f"review_note_{signal_id}"
  apply_key = f"review_apply_{signal_id}"

  if decision_key not in st.session_state:
    st.session_state[decision_key] = str(review.get("review_decision", "保留") or "保留")
  if priority_key not in st.session_state:
    st.session_state[priority_key] = review_priority_label_ja(review.get("review_priority", 2)) or "中"
  if comment_key not in st.session_state:
    st.session_state[comment_key] = str(review.get(REVIEW_COMMENT_FIELD, "") or "")

  return decision_key, priority_key, comment_key, apply_key


def _render_review_input(signal: dict[str, Any], signal_id: str) -> None:
  reviews_by_signal_id = dict(st.session_state.get("reviews_by_signal_id", {}) or {})
  review = _get_review_for_signal(signal, signal_id, reviews_by_signal_id)
  decision_key, priority_key, comment_key, apply_key = _ensure_review_widget_defaults(signal_id, review)

  st.selectbox(
    "レビュー判断",
    options=["採用", "保留", "見送り"],
    key=decision_key,
  )
  st.selectbox(
    "優先度",
    options=["高", "中", "低"],
    key=priority_key,
  )
  st.text_area(
    REVIEW_COMMENT_LABEL_JA,
    key=comment_key,
    height=100,
    placeholder="例: Seed公報と関係がありそうなので、今週確認する。",
  )

  applied_review = review
  if st.button("レビューを反映", key=apply_key, width="stretch"):
    applied_review = normalize_review_state(
      {
        "review_decision": st.session_state.get(decision_key, "保留"),
        "review_priority": review_priority_value_ja(st.session_state.get(priority_key, "中")),
        REVIEW_COMMENT_FIELD: st.session_state.get(comment_key, ""),
        "reviewed": True,
      }
    )
    updated_reviews = dict(reviews_by_signal_id)
    updated_reviews[signal_id] = applied_review
    st.session_state["reviews_by_signal_id"] = updated_reviews
    st.success("レビューを反映しました。")

  if applied_review.get("reviewed"):
    st.write("**レビュー済み**")
    st.write(f"判断: {applied_review.get('review_decision', '保留')}")
    st.write(f"優先度: {review_priority_label_ja(applied_review.get('review_priority', 2)) or '中'}")
    st.write(f"コメント: {applied_review.get(REVIEW_COMMENT_FIELD) or 'なし'}")
  else:
    st.caption("未レビュー")


def _review_progress(summary: dict[str, int] | None) -> dict[str, float | int]:
  payload = summary or {}
  total_count = max(int(payload.get("合計", 0) or 0), 0)
  unreviewed_count = max(int(payload.get("未レビュー", 0) or 0), 0)
  reviewed_count = max(total_count - unreviewed_count, 0)
  ratio = (reviewed_count / total_count) if total_count else 0.0
  ratio = min(max(ratio, 0.0), 1.0)
  return {
    "reviewed_count": reviewed_count,
    "total_count": total_count,
    "ratio": ratio,
    "percent": int(round(ratio * 100)),
  }


def _select_adopted_signals(
  signals: list[dict[str, Any]] | None,
  limit: int = 10,
) -> list[dict[str, Any]]:
  ranked = sort_signals_by_review(list(signals or []))
  adopted = [
    signal for signal in ranked
    if isinstance(signal.get("review"), dict)
    and str(signal["review"].get("review_decision", "") or "") == "採用"
  ]
  return adopted[:max(limit, 0)]


def _select_unreviewed_signals(
  signals: list[dict[str, Any]] | None,
  limit: int = 10,
) -> list[dict[str, Any]]:
  ranked = sort_signals_by_review(list(signals or []))
  unreviewed = [
    signal for signal in ranked
    if isinstance(signal.get("review"), dict)
    and not bool(signal["review"].get("reviewed", False))
  ]
  return unreviewed[:max(limit, 0)]


def render_theme_setup_tab(
  profile_summary: dict[str, object],
  search_plan_state: dict[str, Any],
  profile_status_message: str | None = None,
  search_plan_status_message: str | None = None,
) -> dict[str, bool]:
  st.subheader("Tech Cartography v9")
  st.caption("軽量R&Dシグナル監視エージェント")

  upper_left, upper_right = st.columns(2)
  with upper_left:
    st.text_input("テーマ名", key="ui_theme_name_input")
    st.text_area("テーマ説明", key="ui_theme_description_input", height=160)
    st.text_area(
      "コアキーワード 英語",
      key="ui_core_en_input",
      height=160,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )
    st.text_area(
      "用途キーワード 英語",
      key="ui_application_en_input",
      height=140,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )
    st.text_area(
      "材料・プロセスキーワード 英語",
      key="ui_material_process_en_input",
      height=180,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )
    st.text_area(
      "除外キーワード 英語",
      key="ui_exclude_en_input",
      height=120,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )
  with upper_right:
    st.checkbox("デモモード", key="ui_demo_mode_input")
    st.markdown("**外部API:** 停止中")
    st.markdown("**外部検索:** OFF")
    st.markdown("**実行モード:** ローカルのデモデータ / アップロードCSV/JSONのみ")
    st.markdown("**メール / スケジューラ:** プレビューのみ / 停止中")
    st.caption("現在はローカル実行のみです。BigQuery、OpenAlex、Web検索、Gemini APIは実行しません。")
    st.text_area(
      "コアキーワード 日本語",
      key="ui_core_ja_input",
      height=160,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )
    st.text_area(
      "用途キーワード 日本語",
      key="ui_application_ja_input",
      height=140,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )
    st.text_area(
      "材料・プロセスキーワード 日本語",
      key="ui_material_process_ja_input",
      height=180,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )
    st.text_area(
      "除外キーワード 日本語",
      key="ui_exclude_ja_input",
      height=120,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )

  pub_left, pub_right = st.columns(2)
  with pub_left:
    st.text_area(
      "Seed publication numbers",
      key="ui_seed_publications_input",
      height=120,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )
  with pub_right:
    st.text_area(
      "追加候補 publication numbers",
      key="ui_candidate_publications_input",
      height=120,
      help="カンマ区切り・改行区切りのどちらでも入力できます。",
    )

  button_left, button_mid, button_right = st.columns(3)
  with button_left:
    save_clicked = st.button("監視プロファイルを保存", key="btn_theme_save_profile", width="stretch")
  with button_mid:
    load_clicked = st.button("保存済み監視プロファイルを読み込む", key="btn_theme_load_profile", width="stretch")
  with button_right:
    regenerate_clicked = st.button("検索計画を再生成", key="btn_theme_regenerate_search_plan", width="stretch")

  _show_status_message(profile_status_message)
  _show_status_message(search_plan_status_message)
  st.markdown("### 検索計画状態")
  st.write(f"- 最終生成: {search_plan_state.get('generated_at', '未生成')}")
  st.write(
    f"- Watch Profile signature一致: "
    f"{bool_label_ja(not bool(search_plan_state.get('profile_signature_changed', False)))}"
  )
  st.write(
    f"- 設定変更の未反映: "
    f"{bool_label_ja(bool(search_plan_state.get('settings_signature_changed', False)))}"
  )
  if search_plan_state.get("stale"):
    st.warning("現在の検索計画は最新のWatch Profileまたは設定をまだ反映していません。")
  else:
    st.success("現在の検索計画は最新の入力と一致しています。")
  _render_profile_summary(profile_summary)
  return {
    "save_profile": save_clicked,
    "load_profile": load_clicked,
    "regenerate_search_plan": regenerate_clicked,
  }


def render_sources_tab(
  source_rows: Sequence[dict[str, object]],
  operation_rows: Sequence[dict[str, str]],
  source_info: dict[str, object],
  csv_template_text: str,
  json_template_text: str,
  search_plan_state: dict[str, Any],
  retrieval_reload_state: dict[str, object],
  retrieval_manifest_status_message: str | None = None,
  search_plan_status_message: str | None = None,
  patent_bigquery_state: dict[str, Any] | None = None,
  patent_bigquery_status_message: str | None = None,
  patent_retrieval_status_message: str | None = None,
  paper_openalex_state: dict[str, Any] | None = None,
  paper_retrieval_status_message: str | None = None,
  global_web_retrieval_state: dict[str, Any] | None = None,
  global_web_retrieval_status_message: str | None = None,
  *,
  study_demo_authenticated: bool = False,
) -> dict[str, object]:
  st.subheader("情報源")
  study_events: dict[str, object] = {}
  study_demo_mode = False
  try:
    from services_v9.study_demo_config import is_study_demo_mode
    from ui_v9.study_demo_search_ui import render_study_demo_keyword_search_section

    study_demo_mode = is_study_demo_mode()
    if study_demo_mode:
      study_events = render_study_demo_keyword_search_section(authenticated=study_demo_authenticated)
      st.divider()
  except Exception:
    study_events = {}
  st.caption("特許・論文・Web情報・企業情報を、軽量なローカル / 準備中データとして表示します。")
  if study_demo_mode:
    with st.expander("その他のデータソース", expanded=False):
      st.radio(
        "データ投入モード",
        options=["unselected", "temporary_search", "legacy_demo", "csv", "json", "retrieval_saved"],
        format_func=data_source_mode_label_ja,
        key="ui_data_source_mode",
        horizontal=True,
      )
      if st.button("架空デモ12件を表示", key="btn_show_legacy_demo_12"):
        st.session_state["ui_data_source_mode"] = "legacy_demo"
        study_events["legacy_demo_selected"] = True
      st.caption("Active Analysis Contextの設定は上の「分析対象として使用」から行います。ここは補助的な表示切替です。")
  else:
    st.radio(
      "データ投入モード",
      options=["demo", "csv", "json", "retrieval_saved"],
      format_func=data_source_mode_label_ja,
      key="ui_data_source_mode",
      horizontal=True,
    )
  st.caption(f"現在のデータ投入モード: {data_source_mode_label_ja(str(source_info['requested_mode']))}")
  st.info(
    "ページ表示だけでは外部検索や保存済みmanifest読込を実行しません。アップロードされたCSV/JSONの仮スコア表示に加えて、"
    "特許 / 論文 / Global Web の取得と保存済み結果の読込は明示ボタン時のみ実行します。"
  )

  st.markdown("### 保存済み取得結果")
  _show_status_message(retrieval_manifest_status_message)
  manifest_summary = dict(retrieval_reload_state.get("manifest_summary", {}) or {})
  current_run_ids = dict(retrieval_reload_state.get("current_run_ids", {}) or {})
  st.write(f"- Watch Profile signature: `{str(retrieval_reload_state.get('watch_profile_signature', '') or '')[:8]}`")
  st.write(f"- 現在session内の特許run ID: `{current_run_ids.get('patent', '') or 'なし'}`")
  st.write(f"- 現在session内の論文run ID: `{current_run_ids.get('paper', '') or 'なし'}`")
  st.write(f"- 現在session内のWeb/企業run ID: `{current_run_ids.get('web_company', '') or 'なし'}`")
  if manifest_summary.get("checked"):
    availability_label = "あり" if bool(manifest_summary.get("available")) else "なし"
    st.write(f"- 保存済みmanifestの有無: `{availability_label}`")
    st.write(f"- manifest status: `{manifest_summary.get('status', 'none')}`")
    st.write(f"- 候補件数: `{int(manifest_summary.get('candidate_count', 0) or 0)}`")
  else:
    st.write("- 保存済みmanifestの有無: `未確認`")
    st.write("- manifest status: `未確認`")
    st.write("- 候補件数: `未確認`")
  retrieval_cols = st.columns(2)
  save_retrieval_manifest = retrieval_cols[0].button("現在の取得runを保存", use_container_width=True)
  load_saved_retrieval_manifest = retrieval_cols[1].button("最新の保存済み取得結果を読み込む", use_container_width=True)

  upload_left, upload_right = st.columns(2)
  with upload_left:
    st.markdown("### CSVアップロード")
    st.file_uploader("CSVファイル", type=["csv"], key="ui_csv_upload")
    st.download_button(
      "CSVテンプレートをダウンロード",
      data=csv_template_text,
      file_name="v9_signal_upload_template.csv",
      mime="text/csv",
      use_container_width=True,
      key="study_demo_download_sources_csv_template",
    )
  with upload_right:
    st.markdown("### JSONアップロード")
    st.file_uploader("JSONファイル", type=["json"], key="ui_json_upload")
    st.download_button(
      "JSONテンプレートをダウンロード",
      data=json_template_text,
      file_name="v9_signal_upload_template.json",
      mime="application/json",
      use_container_width=True,
      key="study_demo_download_sources_json_template",
    )

  st.write(f"- 現在のデータソース: {source_info['label']}")
  st.write(f"- 読み込み件数: {source_info['loaded_count']}件")
  if str(source_info.get("mode", "")) == "temporary_search":
    active_context = dict(source_info.get("active_context", {}) or {})
    if active_context.get("active_search_run_id"):
      st.write(f"- run ID: `{active_context.get('active_search_run_id', '')}`")
  if source_info.get("provisional_scoring"):
    if str(source_info.get("mode", "") or "") == "retrieval_saved":
      st.caption("取得済み候補は既存の統合・重複除去・ランキング処理を再実行した結果です。デモ/CSV/JSONは混在していません。")
    else:
      st.caption("アップロードデータは Watch Profile に基づく仮スコアリング済みです。既存スコアがある場合はその値を尊重します。")
  integration_summary = dict(source_info.get("integration_summary", {}) or {})
  if integration_summary:
    st.markdown("### 統合・重複除去サマリー")
    st.write(
      f"- run_id: `{integration_summary.get('integration_run_id', '')}` | "
      f"raw: `{integration_summary.get('raw_count', 0)}` | "
      f"capped: `{integration_summary.get('capped_count', 0)}` | "
      f"deduped: `{integration_summary.get('deduped_count', 0)}` | "
      f"ranked top100: `{integration_summary.get('ranked_count', 0)}`"
    )
    active_sources = ", ".join(str(item) for item in list(integration_summary.get("active_sources", []) or [])) or "none"
    st.write(f"- active retrieval sources: `{active_sources}`")
  warnings = list(source_info.get("warnings", []))
  if warnings:
    st.markdown("### 読み込み警告")
    for warning in warnings:
      st.warning(str(warning))

  for row in source_rows:
    st.markdown(
      f"- **{type_label_ja(str(row['source_type']))}** | "
      f"有効/無効: `{bool_label_ja(bool(row['enabled']))}` | "
      f"モード: `{source_mode_label_ja(str(row['mode']))}` | "
      f"取得件数: `{row['top_n']}` | 最終更新: `{row['last_updated']}` | メモ: {row['note']}"
    )

  st.markdown("### 個別ステータス")
  for item in operation_rows:
    label = type_label_ja(item["label"]) if item["label"] in {"patent", "paper", "web", "company"} else item["label"]
    st.write(f"- {label}: {source_mode_label_ja(item['mode'])}")

  if integration_summary:
    st.markdown("### 情報源別Top5")
    top_by_source = dict(integration_summary.get("top_by_source", {}) or {})
    for source_type in ("patent", "paper", "web", "company"):
      st.write(f"**{type_label_ja(source_type)} Top5**")
      rows = list(top_by_source.get(source_type, []) or [])
      if not rows:
        st.caption("候補なし")
        continue
      for row in rows[:5]:
        st.write(
          f"- #{row.get('current_rank', '-')} {row.get('title', '')} | "
          f"score `{float(row.get('final_score', row.get('score', 0.0)) or 0.0):.2f}` | "
          f"{row.get('organization', '') or row.get('source_name', '')}"
        )

  plan = dict(search_plan_state.get("plan", {}) or {})
  plan_summary = dict(search_plan_state.get("summary", {}) or {})
  source_plans = dict(plan.get("plans", {}) or {})
  global_web_plan = dict(plan.get("global_web_plan", {}) or {})
  manual_queries = list(search_plan_state.get("manual_queries", []) or [])
  manual_queries_by_source: dict[str, list[dict[str, object]]] = {
    "patent": [query for query in manual_queries if str(query.get("source", "") or "") == "patent"],
    "paper": [query for query in manual_queries if str(query.get("source", "") or "") == "paper"],
    "web": [query for query in manual_queries if str(query.get("source", "") or "") == "web"],
    "company": [query for query in manual_queries if str(query.get("source", "") or "") == "company"],
    "global_web": [query for query in manual_queries if str(query.get("source", "") or "") == "global_web"],
  }

  st.markdown("### 統合検索計画サマリー")
  _show_status_message(search_plan_status_message)
  st.info("ここで表示するのは検索実行前のPreviewです。ページを開くだけでは外部APIは実行しません。")
  st.code(str(plan_summary.get("plan_summary_text", "検索計画はまだ生成されていません。")))
  summary_metrics = st.columns(4)
  summary_metrics[0].metric("Discovery query数", f"{int(plan_summary.get('discovery_query_count', 0) or 0)}件")
  summary_metrics[1].metric("Verification予定件数", f"{int(plan_summary.get('verification_planned_count', 0) or 0)}件")
  summary_metrics[2].metric("翻訳予定件数", f"{int(plan_summary.get('translation_planned_count', 0) or 0)}件")
  summary_metrics[3].metric(
    "Global Web enabled",
    f"{int(global_web_plan.get('enabled_query_count', 0) or 0)}件",
  )

  with st.expander("検索計画設定", expanded=False):
    limits_left, limits_right = st.columns(2)
    with limits_left:
      st.number_input("最大取得件数", min_value=100, max_value=5000, step=100, key="ui_search_total_limit")
      st.selectbox("time range", options=["1m", "3m", "6m", "12m", "24m"], key="ui_search_time_range")
    with limits_right:
      st.caption("情報源別件数")
      st.number_input("特許件数", min_value=0, max_value=5000, step=10, key="ui_search_patent_limit")
      st.number_input("論文件数", min_value=0, max_value=5000, step=10, key="ui_search_paper_limit")
      st.number_input("Web件数", min_value=0, max_value=5000, step=10, key="ui_search_web_limit")
      st.number_input("企業件数", min_value=0, max_value=5000, step=10, key="ui_search_company_limit")

    st.caption("Global Web max results")
    max_cols = st.columns(3)
    with max_cols[0]:
      st.number_input("web high max results", min_value=1, max_value=100, step=1, key="ui_search_web_high_max_results")
      st.number_input("web medium max results", min_value=1, max_value=100, step=1, key="ui_search_web_medium_max_results")
    with max_cols[1]:
      st.number_input("web low max results", min_value=1, max_value=100, step=1, key="ui_search_web_low_max_results")
      st.number_input("company high max results", min_value=1, max_value=100, step=1, key="ui_search_company_high_max_results")
    with max_cols[2]:
      st.number_input("company medium max results", min_value=1, max_value=100, step=1, key="ui_search_company_medium_max_results")
      st.number_input("company low max results", min_value=1, max_value=100, step=1, key="ui_search_company_low_max_results")

    st.markdown("#### Web intent ON/OFF")
    intent_labels = {
      "research_development": "research_development",
      "investment_production": "investment_production",
      "partnership_project": "partnership_project",
      "product_commercialization": "product_commercialization",
      "organization_recruitment": "organization_recruitment",
      "regulation_standard": "regulation_standard",
    }
    intent_columns = st.columns(3)
    for index, (intent, label) in enumerate(intent_labels.items()):
      with intent_columns[index % 3]:
        st.checkbox(label, key=_search_intent_enabled_key(intent))

    st.markdown("#### 国・地域ON/OFF / priority / 公式情報優先 / English fallback")
    for country in list(global_web_plan.get("countries", []) or []):
      country_code = str(country.get("country_region_code", "") or "")
      country_name = str(country.get("country_region_name_ja", "") or "")
      country_cols = st.columns([2, 1, 1, 1])
      with country_cols[0]:
        st.checkbox(f"{country_code} {country_name}", key=_search_country_enabled_key(country_code))
      with country_cols[1]:
        st.number_input(
          f"{country_code} priority",
          min_value=1,
          max_value=20,
          step=1,
          key=_search_country_priority_key(country_code),
        )
      with country_cols[2]:
        st.checkbox(f"{country_code} 公式情報優先", key=_search_country_official_key(country_code))
      with country_cols[3]:
        st.checkbox(f"{country_code} English fallback", key=_search_country_fallback_key(country_code))

    regenerate_from_sources = st.button("情報源設定で検索計画を再生成", key="btn_sources_regenerate_search_plan", width="stretch")

  _render_country_coverage(list(plan_summary.get("country_coverage", [])))
  _render_search_plan_provider_routing(list(plan_summary.get("provider_routing", [])))
  _render_search_plan_validation(list(plan_summary.get("validation_errors", [])))

  st.markdown("### 手動query追加")
  manual_source = st.selectbox(
    "手動queryの対象",
    options=["patent", "paper", "web", "company", "global_web"],
    format_func=lambda value: "Global Web" if value == "global_web" else type_label_ja(value),
    key="ui_manual_query_source",
  )
  st.text_input("手動query strategy", key="ui_manual_query_strategy")
  add_manual_query_clicked = False
  if manual_source == "global_web":
    manual_cols = st.columns(3)
    with manual_cols[0]:
      st.selectbox("country_region_code", options=[str(item.get("country_region_code", "")) for item in list(global_web_plan.get("countries", [])) or []], key="ui_manual_query_country")
      st.selectbox(
        "web_intent",
        options=[
          "research_development",
          "investment_production",
          "partnership_project",
          "product_commercialization",
          "organization_recruitment",
          "regulation_standard",
        ],
        key="ui_manual_query_intent",
      )
    with manual_cols[1]:
      st.selectbox("result_bucket", options=["web", "company"], key="ui_manual_query_bucket")
      st.selectbox("priority", options=["high", "medium", "low"], key="ui_manual_query_priority")
    with manual_cols[2]:
      st.number_input("manual max results", min_value=1, max_value=100, step=1, key="ui_manual_query_max_results")
    st.text_input("query_local", key="ui_manual_query_local")
    st.text_input("query_english_fallback", key="ui_manual_query_fallback")
    add_manual_query_clicked = st.button("Global Web手動queryを追加", key="btn_add_manual_global_web_query", width="stretch")
  else:
    st.selectbox("手動query language", options=["ja", "en", "mixed"], key="ui_manual_query_language")
    st.text_input("query_text", key="ui_manual_query_text")
    add_manual_query_clicked = st.button("手動queryを追加", key="btn_add_manual_query", width="stretch")

  delete_manual_query_ids: list[str] = []
  run_patent_dry_run = False
  approve_patent_query = False
  run_patent_retrieval = False
  run_paper_retrieval = False
  run_global_web_retrieval = False
  with st.expander("特許計画", expanded=False):
    patent_plan = dict(source_plans.get("patent", {}) or {})
    st.caption(f"最大件数: {patent_plan.get('limit', 0)}件")
    for note in list(patent_plan.get("notes", []) or []):
      st.write(f"- {note}")
    _render_generated_queries("patent", list(patent_plan.get("queries", []) or []))
    delete_manual_query_ids.extend(_render_manual_queries("patent", manual_queries_by_source["patent"]))
    patent_bigquery_events = _render_patent_bigquery_preview(
      dict(patent_bigquery_state or {}),
      patent_bigquery_status_message,
      patent_retrieval_status_message,
    )
    run_patent_dry_run = bool(patent_bigquery_events.get("run_patent_dry_run"))
    approve_patent_query = bool(patent_bigquery_events.get("approve_patent_query"))
    run_patent_retrieval = bool(patent_bigquery_events.get("run_patent_retrieval"))
  with st.expander("論文計画", expanded=False):
    paper_plan = dict(source_plans.get("paper", {}) or {})
    st.caption(f"最大件数: {paper_plan.get('limit', 0)}件")
    for note in list(paper_plan.get("notes", []) or []):
      st.write(f"- {note}")
    _render_generated_queries("paper", list(paper_plan.get("queries", []) or []))
    delete_manual_query_ids.extend(_render_manual_queries("paper", manual_queries_by_source["paper"]))
    run_paper_retrieval = _render_paper_openalex_preview(
      dict(paper_openalex_state or {}),
      paper_retrieval_status_message,
    )
  delete_manual_query_ids.extend(
    _render_source_plan_expander("Web計画", "web", dict(source_plans.get("web", {}) or {}), manual_queries_by_source["web"])
  )
  delete_manual_query_ids.extend(
    _render_source_plan_expander("企業計画", "company", dict(source_plans.get("company", {}) or {}), manual_queries_by_source["company"])
  )
  with st.expander("Global Web計画", expanded=False):
    st.caption(
      f"time range: {global_web_plan.get('time_range', 'n/a')} | "
      f"Web budget: {global_web_plan.get('web_limit', 0)} | Company budget: {global_web_plan.get('company_limit', 0)}"
    )
    _render_generated_queries("global_web", list(global_web_plan.get("queries", []) or []))
    delete_manual_query_ids.extend(_render_manual_queries("global_web", manual_queries_by_source["global_web"]))
    run_global_web_retrieval = _render_global_web_retrieval_preview(
      dict(global_web_retrieval_state or {}),
      global_web_retrieval_status_message,
    )

  return {
    **study_events,
    "save_retrieval_manifest": save_retrieval_manifest,
    "load_saved_retrieval_manifest": load_saved_retrieval_manifest,
    "regenerate_search_plan": regenerate_from_sources,
    "add_manual_query": add_manual_query_clicked,
    "delete_manual_query_ids": delete_manual_query_ids,
    "run_patent_dry_run": run_patent_dry_run,
    "approve_patent_query": approve_patent_query,
    "run_patent_retrieval": run_patent_retrieval,
    "run_paper_retrieval": run_paper_retrieval,
    "run_global_web_retrieval": run_global_web_retrieval,
  }


def render_top_signals_tab(
  signals: Sequence[Signal],
  display_signals: Sequence[dict[str, Any]],
  source_info: dict[str, object],
  snapshot_status_message: str | None = None,
) -> dict[str, bool]:
  from ui_v9.study_demo_active_banner import render_active_analysis_banner

  st.subheader("注目シグナル")
  render_active_analysis_banner(
    active_context=dict(source_info.get("active_context", {}) or {}) or None,
    downstream_bundle=dict(source_info.get("study_demo_downstream", {}) or {}) or None,
  )
  bundle = dict(source_info.get("study_demo_downstream", {}) or {})
  if str(source_info.get("mode", "")) == "temporary_search" and bundle:
    from services_v9.study_demo_active_loader import adapt_study_demo_signal_to_display

    top_reads = [
      Signal.from_dict(adapt_study_demo_signal_to_display(item, index=index))
      for index, item in enumerate(list(bundle.get("top_reads_raw", []) or []))
    ]
    top_signals = [Signal.from_dict(item) for item in list(bundle.get("display_signals", []) or [])[:10]]
  else:
    top_signals = select_diverse_top_signals(signals, top_n=10, max_per_type=4)
    top_reads = select_top_reads(top_signals, limit=3)
  diversity_counts = build_diversity_counts(signals)
  display_signal_lookup = _build_display_signal_lookup(display_signals)
  score_explanation_lookup = _build_score_explanation_lookup(display_signals)
  st.caption(f"現在のデータソース: {source_info['label']} | 読み込み件数: {source_info['loaded_count']}件")
  if source_info.get("provisional_scoring"):
    st.info("アップロードデータは仮スコアリング済みです。これは外部APIなしの簡易評価です。")

  st.markdown("### 今週まず読むべき3件")
  if not top_reads:
    st.info("今週優先して読む候補はまだありません。")
  else:
    columns = st.columns(len(top_reads))
    for column, signal in zip(columns, top_reads):
      with column:
        explanation = score_explanation_lookup.get(_signal_lookup_key(signal), {})
        related_level = score_level_label_ja(str(explanation.get("score_level", "") or ""))
        related_text = f" | 関連度 {related_level}" if related_level else ""
        st.markdown(f"**{signal.title}**")
        st.caption(
          f"{type_label_ja(signal.type)} | スコア {signal.score:.2f} | "
          f"{status_label_ja(signal.status)} | {action_label_ja(signal.action)}"
          f"{related_text}"
        )
        st.write(signal.why_read)
        st.write(f"確認すべき点: {signal.what_to_check}")
        st.write(f"次の行動: {signal.next_action}")
        from ui_v9.study_demo_source_link import render_external_source_link

        active_context = dict(source_info.get("active_context", {}) or {})
        run_id = str(active_context.get("active_search_run_id", "") or "")
        render_external_source_link(
          signal,
          key_namespace="top_signals_top3",
          search_run_id=run_id,
          label="出典URLを開く",
        )

  available_types = sorted({signal.type for signal in top_signals})
  available_statuses = ["New", "Rising", "Dropped", "Stable"]
  available_actions = ["Read Now", "Watch", "Ignore"]

  filter_left, filter_mid, filter_right = st.columns(3)
  with filter_left:
    selected_types = st.multiselect(
      "種別フィルター",
      available_types,
      default=available_types,
      format_func=type_label_ja,
      key="ui_type_filter",
    )
  with filter_mid:
    selected_statuses = st.multiselect(
      "変化フィルター",
      available_statuses,
      default=available_statuses,
      format_func=status_label_ja,
      key="ui_status_filter",
    )
  with filter_right:
    selected_actions = st.multiselect(
      "判断フィルター",
      available_actions,
      default=available_actions,
      format_func=action_label_ja,
      key="ui_action_filter",
    )

  filtered = [
    signal for signal in top_signals
    if signal.type in selected_types and signal.status in selected_statuses and signal.action in selected_actions
  ]

  diversity_text = " / ".join(
    f"{type_label_ja(signal_type)}: {count}" for signal_type, count in diversity_counts.items()
  )
  st.caption("同じ種別に偏りすぎないように、特許・論文・Web情報・企業情報をバランスよく表示します。")
  st.caption(f"簡易的な多様性制御: {diversity_text}")

  if not filtered:
    st.warning("現在のフィルター条件に一致するシグナルはありません。")
  else:
    st.markdown("### 注目シグナル一覧")
    st.caption(
      "スコア根拠は、現在の監視プロファイルとタイトル・概要・タグなどの簡易キーワード一致に基づく説明です。"
      "技術的妥当性や法的評価を示すものではありません。"
    )
    for index, signal in enumerate(filtered, start=1):
      explanation = score_explanation_lookup.get(_signal_lookup_key(signal), {})
      display_signal = display_signal_lookup.get(_signal_lookup_key(signal), {})
      signal_id = str(display_signal.get("id", "") or "")
      st.markdown(f"#### {index}. {signal.title}")
      st.caption(
        f"種別: {type_label_ja(signal.type)} | スコア: {signal.score:.2f} | "
        f"変化: {status_label_ja(signal.status)} | 判断: {action_label_ja(signal.action)} | "
        f"公開日: {signal.published_date}"
      )
      st.write(f"**なぜ読むべきか:** {signal.why_read}")
      st.write(f"**確認すべき点:** {signal.what_to_check}")
      st.write(f"**次の行動:** {signal.next_action}")
      st.write(f"**出典名:** {signal.source_name}")
      st.write(f"**タグ:** {', '.join(signal.tags) if signal.tags else 'なし'}")
      st.write(f"**関連企業:** {', '.join(signal.companies) if signal.companies else 'なし'}")
      from ui_v9.study_demo_source_link import render_external_source_link

      active_context = dict(source_info.get("active_context", {}) or {})
      run_id = str(active_context.get("active_search_run_id", "") or "")
      render_external_source_link(
        signal,
        key_namespace="top_signals_list",
        search_run_id=run_id,
        label="出典URLを開く",
      )
      with st.expander("スコア根拠を確認", expanded=False):
        _render_score_explanation(explanation)
      with st.expander("人間レビュー", expanded=False):
        _render_review_input(display_signal, signal_id)

  st.text_input("実行メモ", key="ui_snapshot_run_note")
  save_snapshot_clicked = st.button("現在のスナップショットを保存", key="btn_save_snapshot", width="stretch")
  _show_status_message(snapshot_status_message)
  return {"save_snapshot": save_snapshot_clicked}


def render_weekly_updates_tab(
  signals: Sequence[Signal],
  reviewed_signals: Sequence[dict[str, Any]],
  source_info: dict[str, object],
  snapshot_options: Sequence[str],
  diff_result: dict | None,
  drift: dict[str, object],
  history_rows: Sequence[dict[str, str]],
  previous_snapshot_info: dict | None,
  compare_status_message: str | None = None,
) -> dict[str, bool]:
  from ui_v9.study_demo_active_banner import render_active_analysis_banner

  st.subheader("週次更新")
  render_active_analysis_banner(
    active_context=dict(source_info.get("active_context", {}) or {}) or None,
    downstream_bundle=dict(source_info.get("study_demo_downstream", {}) or {}) or None,
  )
  bundle = dict(source_info.get("study_demo_downstream", {}) or {})
  if str(source_info.get("mode", "")) == "temporary_search" and bundle:
    weekly_state = dict(bundle.get("weekly_state", {}) or {})
    st.caption(f"現在の比較対象データ: {source_info['label']} | 読み込み件数: {source_info['loaded_count']}件")
    if weekly_state.get("state") == "initial_baseline":
      st.info("初回ベースライン: 前回比較対象なし。次回runから差分比較できます。")
      confirm = st.checkbox("このrunを初回スナップショットとして保存します", key="ui_study_demo_baseline_confirm")
      save_baseline = st.button("このrunを初回スナップショットとして保存", key="btn_study_demo_save_baseline")
      if save_baseline and not confirm:
        st.error("確認チェックが必要です。")
        save_baseline = False
      diff_result = None
      return {"load_previous_snapshot": False, "compare_snapshot": False, "save_study_demo_baseline": bool(save_baseline and confirm)}
    diff_payload = dict(weekly_state.get("diff", {}) or {})
    counts = dict(diff_payload.get("counts", {}) or {})
    st.markdown("### run間差分")
    for key, label in (
      ("new", "新規"),
      ("disappeared", "消失"),
      ("score_up", "スコア上昇"),
      ("score_down", "スコア低下"),
      ("tier_up", "Tier上昇"),
      ("tier_down", "Tier低下"),
      ("unchanged", "変更なし"),
    ):
      st.write(f"- {label}: {counts.get(key, 0)}件")
    review_summary = dict(bundle.get("review_summary", {}) or {})
    st.markdown("### レビュー状況（active run）")
    st.write(
      f"- accepted: {review_summary.get('accepted', 0)} | pending: {review_summary.get('pending', 0)} | "
      f"rejected: {review_summary.get('rejected', 0)} | unreviewed: {review_summary.get('unreviewed', 0)}"
    )
    exports = dict(bundle.get("digest_exports", {}) or {})
    if exports.get("weekly_diff_csv"):
      from ui_v9.study_demo_download_keys import build_study_demo_download_key

      run_id = str(dict(source_info.get("active_context", {}) or {}).get("active_search_run_id", "") or "")
      st.download_button(
        "Weekly Diff CSV",
        data=exports.get("weekly_diff_csv", ""),
        file_name="weekly_diff.csv",
        key=build_study_demo_download_key("weekly", "weekly_diff_csv", run_id),
      )
    return {"load_previous_snapshot": False, "compare_snapshot": False, "save_study_demo_baseline": False}

  st.caption(f"現在の比較対象データ: {source_info['label']} | 読み込み件数: {source_info['loaded_count']}件")
  st.selectbox(
    "前回スナップショット選択",
    options=list(snapshot_options) if snapshot_options else ["利用可能なスナップショットはありません"],
    key="ui_previous_snapshot_choice",
  )

  button_left, button_right = st.columns(2)
  with button_left:
    load_clicked = st.button("前回スナップショットを読み込む", key="btn_load_previous_snapshot", width="stretch")
  with button_right:
    compare_clicked = st.button("現在データと比較", key="btn_compare_snapshot", width="stretch")

  _show_status_message(compare_status_message)
  if previous_snapshot_info:
    st.caption(
      f"読み込み中の前回スナップショット: {previous_snapshot_info.get('snapshot_id', 'n/a')} "
      f"（{previous_snapshot_info.get('created_at', 'n/a')}）"
    )

  if diff_result:
    counts = diff_result["counts"]
    metrics = st.columns(4)
    for column, status in zip(metrics, ("New", "Rising", "Dropped", "Stable")):
      column.metric(status_label_ja(status), counts.get(status, 0))

    st.markdown("### 前回Digestとの差分サマリー")
    st.write(diff_result["summary"])
    for status in ("New", "Rising", "Dropped", "Stable"):
      items = diff_result["buckets"].get(status, [])
      if not items:
        st.write(f"- **{status_label_ja(status)}**: 0件")
        continue
      lead = items[0]
      title = lead.get("title", "タイトルなし")
      score_text = ""
      if "score" in lead:
        try:
          signal = Signal.from_dict(lead)
          score_text = f" | {format_score_delta(signal)}"
        except Exception:
          score_text = ""
      st.write(f"- **{status_label_ja(status)}**: {len(items)}件 | 代表シグナル: {title}{score_text}")

    st.markdown("### 前回から消えたシグナル")
    missing_signals = diff_result.get("missing_signals", [])
    if not missing_signals:
      st.write("- 前回から消えたシグナルはありません。")
    else:
      for item in missing_signals:
        st.write(f"- {item.get('title', 'タイトルなし')} | 前回スコア: {item.get('score', 'n/a')}")
  else:
    buckets = summarize_status_buckets(signals)
    metrics = st.columns(4)
    for column, status in zip(metrics, ("New", "Rising", "Dropped", "Stable")):
      column.metric(status_label_ja(status), len(buckets[status]))
    st.info("前回スナップショットを読み込んで比較すると、差分サマリーを表示できます。")

  current_reviews_by_signal_id = dict(st.session_state.get("reviews_by_signal_id", {}) or {})
  review_signal_list = apply_reviews_to_signals([dict(signal) for signal in reviewed_signals], current_reviews_by_signal_id)
  review_summary = summarize_reviews(review_signal_list)
  review_progress = _review_progress(review_summary)
  adopted_signals = _select_adopted_signals(review_signal_list, limit=10)
  unreviewed_signals = _select_unreviewed_signals(review_signal_list, limit=10)

  st.markdown("### レビュー状況")
  review_metrics = st.columns(5)
  review_metrics[0].metric("採用", f"{review_summary['採用']}件")
  review_metrics[1].metric("保留", f"{review_summary['保留']}件")
  review_metrics[2].metric("見送り", f"{review_summary['見送り']}件")
  review_metrics[3].metric("未レビュー", f"{review_summary['未レビュー']}件")
  review_metrics[4].metric("合計", f"{review_summary['合計']}件")
  st.caption(
    "未レビュー件数は、人間が「レビューを反映」していないSignalの件数です。"
    "未レビューSignalにもシステム判断に基づく初期分類が表示されています。"
  )
  st.write(
    f"**レビュー進捗:** {review_progress['percent']}%（"
    f"{review_progress['reviewed_count']} / {review_progress['total_count']}件）"
  )
  st.progress(float(review_progress["ratio"]))

  st.markdown("### 採用したシグナル")
  if not adopted_signals:
    st.write("採用されたシグナルはありません。")
  else:
    adopted_total_count = sum(
      1
      for signal in review_signal_list
      if isinstance(signal.get("review"), dict)
      and str(signal["review"].get("review_decision", "") or "") == "採用"
    )
    if adopted_total_count > len(adopted_signals):
      st.caption("件数が多いため、上位10件のみ表示しています。")
    for index, signal in enumerate(adopted_signals, start=1):
      review = dict(signal.get("review", {}) or {})
      st.write(f"{index}. {signal.get('title', 'タイトルなし')}")
      st.write(f"- 種別: {type_label_ja(str(signal.get('type', '') or ''))}")
      st.write(f"- スコア: {float(signal.get('score', 0.0) or 0.0):.2f}")
      st.write(f"- 優先度: {review_priority_label_ja(review.get('review_priority', 2)) or '中'}")
      st.write(f"- 状態: {'レビュー済み' if review.get('reviewed') else '未レビュー'}")
      st.write(f"- コメント: {review.get(REVIEW_COMMENT_FIELD) or 'なし'}")

  st.markdown("### 未レビューのシグナル")
  if not unreviewed_signals:
    st.write("すべてのシグナルがレビュー済みです。")
  else:
    if review_summary["未レビュー"] > len(unreviewed_signals):
      st.caption("件数が多いため、上位10件のみ表示しています。")
    for index, signal in enumerate(unreviewed_signals, start=1):
      review = dict(signal.get("review", {}) or {})
      st.write(f"{index}. {signal.get('title', 'タイトルなし')}")
      st.write(f"- 種別: {type_label_ja(str(signal.get('type', '') or ''))}")
      st.write(f"- システム判断: {action_label_ja(str(signal.get('action', '') or ''))}")
      st.write(f"- 初期レビュー判断: {str(review.get('review_decision', '保留') or '保留')}")
      st.write(f"- スコア: {float(signal.get('score', 0.0) or 0.0):.2f}")

  st.markdown("### テーマずれアラート")
  if drift["level"] == "warning":
    st.warning(str(drift["message"]))
  elif drift["level"] == "success":
    st.success(str(drift["message"]))
  else:
    st.info(str(drift["message"]))
  if drift["examples"]:
    st.caption("監視キーワードとの一致が弱い例: " + " / ".join(str(item) for item in drift["examples"]))

  st.markdown("### 週次run履歴")
  if not history_rows:
    st.write("- 保存済みrun履歴はまだありません。")
  else:
    for row in history_rows:
      st.write(f"- {row['snapshot_id']} | {row['created_at']} | メモ: {row['run_note'] or 'なし'}")

  return {
    "load_previous_snapshot": load_clicked,
    "compare_snapshot": compare_clicked,
  }


def render_watch_profile_tab(
  watch_profile: WatchProfile,
  profile_summary: dict[str, object],
  query_previews: dict[str, str],
  suggestions: Sequence[str],
  weekly_delivery_state: dict[str, object],
  profile_status_message: str | None = None,
  weekly_delivery_status_message: str | None = None,
  *,
  source_info: dict[str, object] | None = None,
) -> dict[str, bool]:
  from ui_v9.study_demo_active_banner import render_active_analysis_banner

  st.subheader("監視プロファイル")
  render_active_analysis_banner(
    active_context=dict((source_info or {}).get("active_context", {}) or {}) or None,
    downstream_bundle=dict((source_info or {}).get("study_demo_downstream", {}) or {}) or None,
  )
  bundle = dict((source_info or {}).get("study_demo_downstream", {}) or {})
  try:
    from services_v9.study_demo_config import is_study_demo_mode

    study_demo = is_study_demo_mode()
  except Exception:
    study_demo = False
  if study_demo and str((source_info or {}).get("mode", "")) != "temporary_search":
    st.warning("分析対象の一時検索runが未選択です。情報源タブで設定してください。")
    return {
      "save_profile": False,
      "load_profile": False,
      "apply_suggestions": False,
      "save_weekly_delivery_settings": False,
      "inspect_scheduler": False,
      "apply_scheduler": False,
    }
  if str((source_info or {}).get("mode", "")) == "temporary_search" and bundle:
    draft = dict(bundle.get("profile_draft", {}) or {})
    st.markdown("### この検索runから作成した監視プロファイル案")
    st.caption("本番未適用 / 自動監視停止中 / Scheduler未接続")
    st.write(f"**status:** `{draft.get('status', '')}`")
    st.write(f"**theme_name:** {draft.get('theme_name', '')}")
    st.write(f"**theme_description:** {draft.get('theme_description', '')}")
    st.write(f"**keywords_ja:** {draft.get('keywords_ja', '')}")
    st.write(f"**keywords_en:** {draft.get('keywords_en', '')}")
    st.write(f"**exact_phrase:** {draft.get('exact_phrase', '')}")
    st.write(f"**exclude_keywords:** {draft.get('exclude_keywords', '')}")
    st.write(f"**seed_patents:** {', '.join(draft.get('seed_patents', []) or []) or 'なし'}")
    st.write(f"**候補企業（自動採用不可）:** {', '.join(draft.get('suggested_companies', []) or []) or 'なし'}")
    st.write(f"**候補国:** {', '.join(draft.get('suggested_countries', []) or []) or 'なし'}")
    st.write(f"**候補CPC/IPC:** {', '.join(draft.get('suggested_cpc_ipc', []) or []) or 'なし'}")
    st.info("勉強会環境では監視プロファイル案の保存のみ可能です。自動週次実行とメール配信は停止しています。")
    return {
      "save_profile": False,
      "load_profile": False,
      "apply_suggestions": False,
      "save_weekly_delivery_settings": False,
      "inspect_scheduler": False,
      "apply_scheduler": False,
    }

  st.text_area(
    "注目企業",
    key="ui_target_companies_input",
    height=90,
    help="カンマ区切り・改行区切りのどちらでも入力できます。",
  )
  st.text_input("対象国", key="ui_countries_input")
  st.multiselect(
    "情報源タイプ",
    options=["patent", "paper", "web", "company"],
    format_func=type_label_ja,
    key="ui_source_types_input",
  )
  st.selectbox(
    "更新頻度",
    options=["weekly", "biweekly", "monthly"],
    format_func=cadence_label_ja,
    key="ui_cadence_input",
  )
  st.text_area(
    "優先ルール",
    key="ui_priority_rules_input",
    height=120,
    help="1行に1件ずつ入力してください。",
  )

  _show_status_message(profile_status_message)

  st.markdown("### 現在の監視プロファイル")
  st.write(f"**テーマ名:** {profile_summary.get('theme_name') or '未設定'}")
  st.write(f"**テーマ説明:** {profile_summary.get('theme_description') or '未設定'}")
  st.write(f"**注目企業:** {', '.join(profile_summary.get('target_companies', [])) or 'なし'}")
  st.write(f"**対象国:** {', '.join(watch_profile.countries) if watch_profile.countries else 'なし'}")
  st.write(f"**情報源タイプ:** {', '.join(type_label_ja(item) for item in watch_profile.source_types)}")
  st.write(f"**更新頻度:** {cadence_label_ja(watch_profile.cadence)}")

  _render_profile_summary(profile_summary)

  st.markdown("### Seed publication numbers")
  if watch_profile.seed_publications:
    for item in watch_profile.seed_publications:
      st.write(f"- {item}")
  else:
    st.write("- なし")

  st.markdown("### 追加候補 publication numbers")
  if watch_profile.candidate_publications:
    for item in watch_profile.candidate_publications:
      st.write(f"- {item}")
  else:
    st.write("- なし")

  st.markdown("### 監視プロファイル更新提案")
  for index, suggestion in enumerate(suggestions, start=1):
    st.write(f"提案{index}: {watch_profile_suggestion_label_ja(suggestion)}")

  st.markdown("### 簡易検索クエリPreview")
  st.caption("これは検索実行ではなくPreviewです。外部APIや外部検索は実行しません。")
  for label, key in [
    ("特許検索Preview", "patent"),
    ("論文検索Preview", "paper"),
    ("Web検索Preview", "web"),
    ("企業情報検索Preview", "company"),
  ]:
    with st.expander(label):
      st.code(query_previews.get(key, "Previewを生成できませんでした。"))

  settings = dict(weekly_delivery_state.get("settings", {}) or {})
  validation = dict(weekly_delivery_state.get("validation", {}) or {})
  scheduler_status = dict(weekly_delivery_state.get("scheduler_status", {}) or {})
  scheduler_admin_enabled = bool(weekly_delivery_state.get("scheduler_admin_enabled", False))
  masked_recipient = str(weekly_delivery_state.get("masked_recipient", "") or "")
  allowed_recipient_label = str(weekly_delivery_state.get("allowed_recipient_label", "") or "")
  state_text = str(scheduler_status.get("state", settings.get("last_scheduler_known_state", "")) or "unknown")

  with st.expander("週次自動配信設定", expanded=True):
    st.caption("保存時だけ設定を書き込みます。Cloud Scheduler API は明示ボタン時だけ呼びます。")
    _show_status_message(weekly_delivery_status_message)
    if scheduler_admin_enabled:
      st.success("クラウド管理機能は有効です。")
    else:
      st.info("クラウド管理機能が無効です。設定保存のみ可能です。")
    st.checkbox("自動配信を有効にする", key="ui_weekly_delivery_enabled")
    st.text_input("送信先メールアドレス", key="ui_weekly_delivery_recipient")
    st.selectbox(
      "実行曜日",
      options=["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"],
      format_func=_weekday_label_ja,
      key="ui_weekly_delivery_weekday",
    )
    time_col1, time_col2 = st.columns(2)
    time_col1.selectbox("実行時刻（時）", options=list(range(24)), key="ui_weekly_delivery_hour")
    time_col2.selectbox("実行時刻（分）", options=list(range(60)), key="ui_weekly_delivery_minute")
    st.selectbox(
      "タイムゾーン",
      options=["Asia/Tokyo", "UTC", "America/New_York", "Europe/London"],
      key="ui_weekly_delivery_timezone",
    )
    st.write(f"- recipient: `{masked_recipient or '未設定'}`")
    st.write(f"- allowlist: `{allowed_recipient_label or '未設定'}`")
    st.write(f"- cron: `{settings.get('cron_expression', '') or '未計算'}`")
    st.write(f"- revision: `{settings.get('revision', 0)}`")
    st.write(f"- scheduler applied revision: `{settings.get('scheduler_applied_revision', 0)}`")
    st.write(f"- 最終更新: `{settings.get('updated_at', '') or '未保存'}`")
    st.write(f"- Scheduler state: `{state_text}`")
    st.write(f"- Scheduler反映結果: `{settings.get('last_scheduler_apply_status', '') or '未反映'}`")
    if int(settings.get("revision", 0) or 0) != int(settings.get("scheduler_applied_revision", 0) or 0):
      st.warning("設定revisionとScheduler反映revisionが一致していません。")
    errors = list(validation.get("errors", []) or [])
    warnings = list(validation.get("warnings", []) or [])
    for message in errors:
      st.error(str(message))
    for message in warnings:
      st.warning(str(message))
    scheduler_button_left, scheduler_button_mid, scheduler_button_right = st.columns(3)
    save_weekly_delivery_settings = scheduler_button_left.button("設定を保存", key="btn_weekly_delivery_save", width="stretch")
    inspect_scheduler = scheduler_button_mid.button("現在のCloud Scheduler設定を確認", key="btn_weekly_delivery_inspect", width="stretch")
    apply_scheduler = scheduler_button_right.button("Cloud Schedulerへ反映", key="btn_weekly_delivery_apply", width="stretch")

  button_left, button_mid, button_right = st.columns(3)
  with button_left:
    load_clicked = st.button("保存済み監視プロファイルを読み込む", key="btn_profile_load", width="stretch")
  with button_mid:
    save_clicked = st.button("監視プロファイルを保存", key="btn_profile_save", width="stretch")
  with button_right:
    apply_clicked = st.button("デモ提案を反映", key="btn_profile_apply", width="stretch")

  return {
    "save_profile": save_clicked,
    "load_profile": load_clicked,
    "apply_suggestions": apply_clicked,
    "save_weekly_delivery_settings": save_weekly_delivery_settings,
    "inspect_scheduler": inspect_scheduler,
    "apply_scheduler": apply_scheduler,
  }


def render_digest_export_tab(
  markdown_text: str,
  csv_text: str,
  json_text: str,
  source_info: dict[str, object],
  email_delivery_state: dict[str, object],
  email_delivery_status_message: str | None = None,
  digest_status_message: str | None = None,
) -> dict[str, bool | str | None]:
  from ui_v9.study_demo_active_banner import render_active_analysis_banner
  from ui_v9.study_demo_event_contracts import default_digest_events

  events = default_digest_events()
  st.subheader("ダイジェスト / エクスポート")
  render_active_analysis_banner(
    active_context=dict(source_info.get("active_context", {}) or {}) or None,
    downstream_bundle=dict(source_info.get("study_demo_downstream", {}) or {}) or None,
  )
  st.caption(f"現在のデータソース: {source_info['label']} | 読み込み件数: {source_info['loaded_count']}件")
  bundle = dict(source_info.get("study_demo_downstream", {}) or {})
  if str(source_info.get("mode", "")) == "temporary_search" and bundle:
    from ui_v9.study_demo_download_keys import build_study_demo_download_key

    exports = dict(bundle.get("digest_exports", {}) or {})
    active_context = dict(source_info.get("active_context", {}) or {})
    run_id = str(active_context.get("active_search_run_id", "") or "")
    markdown_text = str(exports.get("digest_markdown", markdown_text) or markdown_text)
    st.caption("active run artifact再利用 / メール未送信 / 自動週次停止中")
    st.markdown(markdown_text)
    st.download_button(
      "Active Context JSON",
      data=exports.get("active_context_json", "{}"),
      file_name="active_context.json",
      key=build_study_demo_download_key("digest", "active_context_json", run_id),
    )
    st.download_button(
      "Digest Markdown",
      data=exports.get("digest_markdown", ""),
      file_name="study_demo_digest.md",
      key=build_study_demo_download_key("digest", "digest_markdown", run_id),
    )
    st.download_button(
      "Digest JSON",
      data=exports.get("digest_json", "{}"),
      file_name="study_demo_digest.json",
      key=build_study_demo_download_key("digest", "digest_json", run_id),
    )
    st.download_button(
      "Integrated CSV (all tiers)",
      data=exports.get("integrated_csv_all_tiers", ""),
      file_name="integrated_all.csv",
      key=build_study_demo_download_key("digest", "integrated_csv_all_tiers", run_id),
    )
    st.download_button(
      "Weekly Diff CSV",
      data=exports.get("weekly_diff_csv", ""),
      file_name="weekly_diff.csv",
      key=build_study_demo_download_key("digest", "weekly_diff_csv", run_id),
    )
    st.download_button(
      "Profile Draft JSON",
      data=exports.get("profile_draft_json", "{}"),
      file_name="profile_draft.json",
      key=build_study_demo_download_key("digest", "profile_draft_json", run_id),
    )
    st.download_button(
      "Full Provenance JSON",
      data=exports.get("full_provenance_json", "{}"),
      file_name="provenance.json",
      key=build_study_demo_download_key("digest", "full_provenance_json", run_id),
    )
    st.caption("Study Demoではメール送信は無効です。")
    return events

  st.caption("人間レビューが反映済みのSignalは、その判断を優先してダイジェストへ表示します。未レビューSignalはシステム判断に基づいて補完されます。")
  st.caption("現在の人間レビュー情報は、SnapshotとJSON Exportに含まれます。CSV Exportには含まれません。")
  st.markdown(markdown_text)

  button_left, button_mid, button_right = st.columns(3)
  with button_left:
    st.download_button(
      "Markdownをダウンロード",
      data=markdown_text,
      file_name="tech_cartography_v9_weekly_digest.md",
      mime="text/markdown",
      use_container_width=True,
      key="study_demo_download_digest_markdown_legacy",
    )
  with button_mid:
    st.download_button(
      "CSVをダウンロード",
      data=csv_text,
      file_name="tech_cartography_v9_top_signals.csv",
      mime="text/csv",
      use_container_width=True,
      key="study_demo_download_digest_csv_legacy",
    )
  with button_right:
    st.download_button(
      "JSONをダウンロード",
      data=json_text,
      file_name="tech_cartography_v9_signal_watch.json",
      mime="application/json",
      use_container_width=True,
      key="study_demo_download_digest_json_legacy",
    )

  save_digest_clicked = st.button("ダイジェストファイルを保存", key="btn_save_digest_files", width="stretch")
  _show_status_message(digest_status_message)

  config = email_delivery_state.get("config")
  preview = dict(email_delivery_state.get("preview", {}) or {})
  dry_run_result = dict(email_delivery_state.get("dry_run_result", {}) or {})
  last_dry_run_result = dict(email_delivery_state.get("last_dry_run_result", {}) or {})
  last_send_result = dict(email_delivery_state.get("last_send_result", {}) or {})
  validation_errors = list(dry_run_result.get("validation_errors", []) or [])
  validation_warnings = list(dry_run_result.get("validation_warnings", []) or [])

  st.markdown("### メール配信")
  _show_status_message(email_delivery_status_message)
  st.write(f"- 現在の送信モード: `{getattr(config, 'send_mode', '')}`")
  st.write(f"- 送信停止フラグ: `{'true' if bool(getattr(config, 'disabled', True)) else 'false'}`")
  st.write(f"- 自分宛て送信先: `{getattr(config, 'self_recipient', '') or '未設定'}`")
  st.write(f"- データソース: `{preview.get('data_source', '')}`")
  st.write(f"- 送信可否: `{dry_run_result.get('status', 'blocked')}`")
  if validation_errors:
    st.markdown("#### 送信エラー")
    for message in validation_errors:
      st.error(str(message))
  if validation_warnings:
    st.markdown("#### 送信警告")
    for message in validation_warnings:
      st.warning(str(message))
  st.write(f"- メール件名: `{preview.get('subject', '')}`")
  st.markdown("#### Plain Text Preview")
  st.code(str(preview.get("plain_text_body", "") or ""))
  st.markdown("#### HTML Preview")
  st.markdown(str(preview.get("html_body", "") or ""), unsafe_allow_html=True)
  st.checkbox(
    "現在のPreview内容を自分宛てに送信することを確認しました",
    key="ui_email_confirm_send",
  )
  email_button_left, email_button_right = st.columns(2)
  run_email_delivery_dry_run = email_button_left.button("メール送信dry-run", key="btn_email_dry_run", width="stretch")
  send_email_self_only = email_button_right.button(
    "自分宛てにメール送信",
    key="btn_email_send_self_only",
    width="stretch",
    disabled=not bool(st.session_state.get("ui_email_confirm_send", False)),
  )
  if last_dry_run_result:
    st.caption(
      f"直近dry-run: status={last_dry_run_result.get('status', '')} / "
      f"recipient={last_dry_run_result.get('recipient_masked', '')}"
    )
  if last_send_result:
    st.caption(
      f"直近送信: status={last_send_result.get('status', '')} / "
      f"recipient={last_send_result.get('recipient_masked', '')}"
    )
  events["save_digest_files"] = bool(save_digest_clicked)
  events["run_email_delivery_dry_run"] = bool(run_email_delivery_dry_run)
  events["send_email_self_only"] = bool(send_email_self_only)
  return events
