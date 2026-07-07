"""Simple Mode weekly, watch profile, and digest tabs for Study Demo."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import streamlit as st

from services_v9.signal_models import Signal
from services_v9.study_demo_ui_mode import should_show_technical_ids
from ui_v9.labels import cadence_label_ja, type_label_ja, watch_profile_suggestion_label_ja
from ui_v9.study_demo_compact_components import render_signal_card_simple
from ui_v9.study_demo_event_contracts import default_digest_events


def select_top_reads_from_bundle(bundle: Mapping[str, Any]) -> list[Signal]:
  from services_v9.study_demo_active_loader import adapt_study_demo_signal_to_display

  raw = list(bundle.get("top_reads_raw", []) or [])
  if raw:
    return [Signal.from_dict(adapt_study_demo_signal_to_display(item, index=index)) for index, item in enumerate(raw)]
  display = [Signal.from_dict(item) for item in list(bundle.get("display_signals", []) or [])[:3]]
  return display


def render_simple_weekly_tab(*, source_info: Mapping[str, object]) -> dict[str, bool]:
  bundle = dict(source_info.get("study_demo_downstream", {}) or {})
  weekly_state = dict(bundle.get("weekly_state", {}) or {})
  metrics = dict(source_info.get("canonical_metrics", {}) or {})
  integrated = metrics.get("integrated_count", source_info.get("loaded_count", 0))

  if weekly_state.get("state") == "initial_baseline":
    st.info("今回は初回ベースラインです。次回runから比較できます。")
  st.write(f"**取得件数:** {integrated}件")
  st.caption("次回予定: 自動週次は停止中（ハッカソンデモ）")

  if weekly_state.get("state") == "initial_baseline":
    confirm = st.checkbox("このrunを初回スナップショットとして保存します", key="ui_study_demo_baseline_confirm")
    save_baseline = st.button("このrunを初回スナップショットとして保存", key="btn_study_demo_save_baseline")
    if save_baseline and not confirm:
      st.error("確認チェックが必要です。")
      save_baseline = False
    return {"load_previous_snapshot": False, "compare_snapshot": False, "save_study_demo_baseline": bool(save_baseline and confirm)}

  diff_payload = dict(weekly_state.get("diff", {}) or {})
  counts = dict(diff_payload.get("counts", {}) or {})
  if counts:
    st.markdown("#### 前回からの変化")
    for key, label in (("new", "新規"), ("score_up", "スコア上昇"), ("score_down", "スコア低下")):
      st.write(f"- {label}: {counts.get(key, 0)}件")

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
  if draft:
    st.markdown("#### 監視プロファイル案")
    st.write(f"**Theme:** {draft.get('theme_name', profile_summary.get('theme_name', ''))}")
    st.write(f"**対象情報源:** Patent / Paper / Web")
    st.caption("更新頻度: 週次（デモでは自動実行停止中）")
    st.write(f"**注目企業:** {', '.join(draft.get('suggested_companies', []) or []) or 'なし'}")
    if suggestions:
      st.markdown("**改善提案**")
      for index, suggestion in enumerate(suggestions, start=1):
        st.write(f"{index}. {watch_profile_suggestion_label_ja(suggestion)}")
    if st.button("プロファイルを編集", key="btn_simple_profile_edit"):
      st.session_state["ui_simple_profile_edit_open"] = True
    with st.expander("キーワード詳細", expanded=False):
      st.write(f"keywords_ja: {draft.get('keywords_ja', '')}")
      st.write(f"keywords_en: {draft.get('keywords_en', '')}")
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
  if suggestions:
    st.markdown("**改善提案**")
    for index, suggestion in enumerate(suggestions, start=1):
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
  digest_markdown = str(exports.get("digest_markdown", markdown_text) or markdown_text)

  top_signals = select_top_reads_from_bundle(bundle)
  display_signals = list(bundle.get("display_signals", []) or [])
  display_lookup = {
    f"{item.get('type', '')}:{item.get('title', '')}:{item.get('source_name', '')}": item
    for item in display_signals
    if isinstance(item, dict)
  }

  st.markdown("#### 今週読むべき3件")
  if top_signals:
    for index, signal in enumerate(top_signals, start=1):
      key = f"{signal.type}:{signal.title}:{signal.source_name}"
      render_signal_card_simple(
        signal=signal,
        display_signal=display_lookup.get(key, {}),
        explanation={},
        search_run_id=run_id,
        key_namespace="simple_digest_top3",
        index=index,
      )
  else:
    st.caption("ダイジェスト対象シグナルがありません。")

  st.markdown("#### 次に確認すること")
  st.markdown(digest_markdown[:1200] + ("..." if len(digest_markdown) > 1200 else ""))

  from ui_v9.study_demo_download_keys import build_study_demo_download_key

  download_left, download_right = st.columns(2)
  with download_left:
    st.download_button(
      "Digest Markdown",
      data=exports.get("digest_markdown", digest_markdown),
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
    with st.expander("技術者向けDownload", expanded=False):
      st.download_button(
        "Digest JSON",
        data=exports.get("digest_json", "{}"),
        file_name="study_demo_digest.json",
        key=build_study_demo_download_key("digest", "digest_json_simple", run_id),
      )

  return events


__all__ = [
  "render_simple_digest_tab",
  "render_simple_watch_profile_tab",
  "render_simple_weekly_tab",
  "select_top_reads_from_bundle",
]
