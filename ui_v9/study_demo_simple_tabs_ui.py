"""Simple Mode weekly, watch profile, and digest tabs for Study Demo."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import streamlit as st

from services_v9.run_baseline_state import build_baseline_summary, is_initial_baseline
from services_v9.search_improvement_eligibility import build_insufficient_review_message
from services_v9.study_demo_ui_mode import should_show_technical_ids
from services_v9.human_digest_builder import human_digest_to_markdown
from ui_v9.labels import cadence_label_ja, type_label_ja, watch_profile_suggestion_label_ja
from ui_v9.study_demo_event_contracts import default_digest_events


def _filter_simple_suggestions(suggestions: Sequence[str]) -> list[str]:
  blocked_prefixes = (
    "raise priority of source type:",
    "lower priority of irrelevant source:",
  )
  return [item for item in suggestions if not str(item).startswith(blocked_prefixes)]


def render_simple_weekly_tab(*, source_info: Mapping[str, object]) -> dict[str, bool]:
  bundle = dict(source_info.get("study_demo_downstream", {}) or {})
  weekly_state = dict(bundle.get("weekly_state", {}) or {})
  metrics = dict(source_info.get("canonical_metrics", {}) or {})
  integrated = int(metrics.get("integrated_count", source_info.get("loaded_count", 0)) or 0)
  summary = build_baseline_summary(weekly_state)

  if is_initial_baseline(weekly_state):
    st.markdown("#### 週次更新")
    st.success(summary.get("headline", "初回ベースラインを保存しました"))
    st.write(f"**今回取得:** {summary.get('current_count', integrated)}件")
    st.write(f"**優先確認:** {summary.get('priority_count', 3)}件")
    st.write("**比較対象:** なし")
    st.caption(str(summary.get("next_message", "")))
    st.caption("Demo: 自動実行・メール送信は停止中")
    confirm = st.checkbox("このrunを初回スナップショットとして保存します", key="ui_study_demo_baseline_confirm")
    save_baseline = st.button("このrunを初回スナップショットとして保存", key="btn_study_demo_save_baseline")
    if save_baseline and not confirm:
      st.error("確認チェックが必要です。")
      save_baseline = False
    return {"load_previous_snapshot": False, "compare_snapshot": False, "save_study_demo_baseline": bool(save_baseline and confirm)}

  st.markdown("#### 週次更新")
  st.write(f"**今回取得:** {summary.get('current_count', integrated)}件")
  st.write(f"**優先確認:** {summary.get('priority_count', 3)}件")
  st.write(f"**比較対象:** {summary.get('comparison_label', 'あり')}")
  st.caption("Demo: 自動実行・メール送信は停止中")
  counts = dict(summary.get("counts", {}) or {})
  if counts and weekly_state.get("show_diff_counts"):
    st.markdown("#### 前回からの変化")
    for key, label in (("new", "新規"), ("score_up", "順位上昇"), ("score_down", "順位低下")):
      value = int(counts.get(key, 0) or 0)
      if value:
        st.write(f"- {label}: {value}件")

  if should_show_technical_ids():
    with st.expander("技術情報（週次）", expanded=False):
      st.json(weekly_state)

  return {"load_previous_snapshot": False, "compare_snapshot": False, "save_study_demo_baseline": False}


def render_simple_watch_profile_tab(
  *,
  watch_profile: Any,
  profile_summary: Mapping[str, object],
  suggestions: Sequence[str],
  source_info: Mapping[str, object] | None,
) -> dict[str, bool]:
  bundle = dict((source_info or {}).get("study_demo_downstream", {}) or {})
  draft = dict(bundle.get("profile_draft", {}) or {})
  proposals_payload = dict(bundle.get("review_proposals", {}) or {})
  simple_suggestions = _filter_simple_suggestions(suggestions)

  if draft:
    st.markdown("#### 監視プロファイル案")
    st.write(f"**Theme:** {draft.get('theme_name', profile_summary.get('theme_name', ''))}")
    st.write("**対象情報源:** Patent / Paper / Web")
    st.caption("更新頻度: 週次（デモでは自動実行停止中）")
    st.write(f"**注目企業:** {', '.join(draft.get('suggested_companies', []) or []) or 'なし'}")
    if simple_suggestions:
      st.markdown("**改善提案**")
      for index, suggestion in enumerate(simple_suggestions, start=1):
        st.write(f"{index}. {watch_profile_suggestion_label_ja(suggestion)}")
    elif not proposals_payload.get("summary", {}).get("eligible", False):
      st.info(build_insufficient_review_message())
    return {
      "save_profile": False,
      "load_profile": False,
      "apply_suggestions": False,
      "save_weekly_delivery_settings": False,
      "inspect_scheduler": False,
      "apply_scheduler": False,
    }

  st.markdown("#### 監視プロファイル")
  st.write(f"**Theme:** {profile_summary.get('theme_name') or '未設定'}")
  st.write(f"**対象情報源:** {', '.join(type_label_ja(item) for item in watch_profile.source_types)}")
  st.write(f"**更新頻度:** {cadence_label_ja(watch_profile.cadence)}")
  st.write(f"**対象国:** {', '.join(watch_profile.countries) if watch_profile.countries else 'なし'}")
  st.write(f"**注目企業:** {', '.join(profile_summary.get('target_companies', [])) or 'なし'}")
  if simple_suggestions:
    st.markdown("**改善提案**")
    for index, suggestion in enumerate(simple_suggestions, start=1):
      st.write(f"{index}. {watch_profile_suggestion_label_ja(suggestion)}")
  return {
    "save_profile": False,
    "load_profile": False,
    "apply_suggestions": False,
    "save_weekly_delivery_settings": False,
    "inspect_scheduler": False,
    "apply_scheduler": False,
  }


def render_simple_digest_tab(
  *,
  markdown_text: str,
  csv_text: str,
  source_info: Mapping[str, object],
) -> dict[str, bool | str | None]:
  events = default_digest_events()
  bundle = dict(source_info.get("study_demo_downstream", {}) or {})
  active_context = dict(source_info.get("active_context", {}) or {})
  run_id = str(active_context.get("active_search_run_id", "") or "")
  exports = dict(bundle.get("digest_exports", {}) or {})
  human_digest = dict(bundle.get("human_digest", {}) or {})
  digest_markdown = str(exports.get("digest_markdown", "") or human_digest_to_markdown(human_digest) or markdown_text)

  st.markdown("#### 今週のR&Dシグナル")
  st.caption("Demo: 自動週次・メール送信は停止中")

  if human_digest:
    st.markdown(f"**テーマ:** {human_digest.get('theme_name', '')}")
    if is_initial_baseline({"state": human_digest.get("baseline_state", "")}):
      st.write("- 初回ベースライン")
    st.write(f"- 実データ {human_digest.get('current_count', 0)}件")
    st.write(f"- 優先確認 {human_digest.get('priority_count', 3)}件")
    st.write(f"- 比較対象 {'なし' if not human_digest.get('has_comparison') else 'あり'}")
    st.markdown("##### 今回まず確認する3件")
    for item in list(human_digest.get("top3", []) or []):
      role = dict(item.get("role", {}) or {})
      st.markdown(f"**{item.get('short_title_ja', '')}** ({role.get('label_ja', '')})")
      st.write(str(item.get("research_value", "") or ""))
      for question in list(item.get("verification_questions", []) or []):
        st.write(f"- {question}")
      st.write(f"読後: {item.get('readout_artifact', '')}")
      if item.get("source_url"):
        st.write(f"[原典を確認]({item.get('source_url')})")
    review = dict(human_digest.get("review_summary", {}) or {})
    st.markdown("##### 人間レビュー")
    st.write(
      f"未判断 {review.get('unreviewed', 0)} | 関連 {review.get('accept', 0)} | "
      f"保留 {review.get('hold', 0)} | 除外 {review.get('reject', 0)}"
    )
  else:
    st.markdown(digest_markdown[:1200] + ("..." if len(digest_markdown) > 1200 else ""))

  from ui_v9.study_demo_download_keys import build_study_demo_download_key

  download_left, download_right = st.columns(2)
  with download_left:
    st.download_button(
      "Digest Markdown",
      data=digest_markdown,
      file_name="study_demo_digest.md",
      key=build_study_demo_download_key("digest", "digest_markdown_simple", run_id),
    )
  with download_right:
    st.download_button(
      "結果CSV",
      data=exports.get("integrated_csv_all_tiers", csv_text),
      file_name="integrated_all.csv",
      key=build_study_demo_download_key("digest", "integrated_csv_simple", run_id),
    )

  if should_show_technical_ids():
    with st.expander("実行証跡", expanded=False):
      st.download_button(
        "Digest JSON",
        data=exports.get("digest_json", "{}"),
        file_name="study_demo_digest.json",
        key=build_study_demo_download_key("digest", "digest_json_simple", run_id),
      )
      st.download_button(
        "Technical Digest Markdown",
        data=exports.get("digest_markdown_technical", ""),
        file_name="study_demo_digest_technical.md",
        key=build_study_demo_download_key("digest", "digest_markdown_technical", run_id),
      )

  return events


__all__ = [
  "render_simple_digest_tab",
  "render_simple_watch_profile_tab",
  "render_simple_weekly_tab",
]
