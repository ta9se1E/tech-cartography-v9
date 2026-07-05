"""Theme draft review/edit/save-as-new UI for Study Demo."""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from services_v9.study_demo_theme_draft import (
  can_generate_plan_for_draft,
  can_generate_watch_profile_for_draft,
  draft_from_editor_payload,
  draft_widget_key,
  should_show_old_plan_warning,
  summarize_theme_draft_state,
  validate_draft_generation_precondition,
  validate_theme_draft,
)
from services_v9.study_demo_theme_lineage import DEFAULT_SAVED_THEME_NAME, build_search_plan_preview_summary


def _ensure_draft_widget_defaults(draft: Mapping[str, Any]) -> None:
  from services_v9.study_demo_theme_draft import draft_editor_defaults

  draft_id = str(draft.get("draft_id", "") or "")
  defaults = draft_editor_defaults(draft)
  for field, value in defaults.items():
    key = draft_widget_key(draft_id, field)
    if key not in st.session_state:
      st.session_state[key] = value


def _read_draft_editor(draft: Mapping[str, Any]) -> dict[str, Any]:
  draft_id = str(draft.get("draft_id", "") or "")
  return {
    field: st.session_state.get(draft_widget_key(draft_id, field))
    for field in (
      "name",
      "description",
      "core_ja",
      "core_en",
      "use_ja",
      "use_en",
      "material_process_ja",
      "material_process_en",
      "exclude_ja",
      "exclude_en",
      "seed_publications",
      "candidate_publications",
      "year_start",
      "year_end",
      "exact_phrase",
      "enable_patent",
      "enable_paper",
      "enable_web",
      "patent_display_limit",
      "paper_display_limit",
      "web_max_results",
    )
  }


def render_theme_draft_section(
  *,
  draft: Mapping[str, Any] | None,
  active_context: Mapping[str, Any] | None,
  saved_theme: Mapping[str, Any] | None,
  search_plan: Mapping[str, Any] | None,
  theme_saved_from_draft: bool = False,
) -> dict[str, Any]:
  st.markdown("### D. 作成した未保存テーマ案")
  events: dict[str, Any] = {
    "keep_draft_changes": False,
    "save_draft_as_new": False,
    "discard_draft": False,
    "draft_editor_payload": None,
    "save_confirmed": False,
    "discard_confirmed": False,
  }
  if not draft:
    st.info("一時検索runから作成された未保存テーマ案はありません。")
    return events

  precondition_errors = validate_draft_generation_precondition(draft, active_context)
  if precondition_errors:
    st.error("分析対象またはテーマ案が別の参加者により更新されました。再読み込みしてください。")
    st.caption("; ".join(precondition_errors))
    return events

  summary = summarize_theme_draft_state(
    draft,
    saved_theme=saved_theme,
    search_plan=search_plan,
    theme_saved=theme_saved_from_draft,
  )
  st.markdown("**状態:** 未保存のテーマ案")
  st.write(f"- Theme draft ID: `{draft.get('draft_id', '')}`")
  st.write(f"- Theme ID: `{draft.get('theme_id', '')}` / version `{draft.get('theme_version', 1)}`")
  st.write(f"- Theme signature: `{str(draft.get('theme_signature', ''))[:8]}`")
  st.write(f"- Theme draft signature: `{summary.get('theme_draft_signature_short', '')}`")
  st.write("- **作成元:** 一時キーワード検索")
  st.write(f"- **元Search Run:** `{draft.get('source_search_run_id', '')}`")
  st.write(f"- source: `{draft.get('source', '')}`")
  st.write(f"- 作成日時: {draft.get('created_at', '')}")
  st.write(f"- 最終編集: {draft.get('updated_at', '')}")
  st.write(f"- 未保存変更: {'あり' if draft.get('dirty') else 'なし'}")
  st.write("- **既存テーマへの影響:** なし")
  st.write("- Active Contextへの影響: なし")
  st.write("- 自動保存: しない")
  st.write("- 自動適用: しない")

  _ensure_draft_widget_defaults(draft)
  draft_id = str(draft.get("draft_id", "") or "")
  st.markdown("#### テーマ案の編集")
  st.text_input("テーマ名", key=draft_widget_key(draft_id, "name"))
  st.text_area("テーマ説明", key=draft_widget_key(draft_id, "description"), height=120)
  col_left, col_right = st.columns(2)
  with col_left:
    st.text_area("コアキーワード 日本語", key=draft_widget_key(draft_id, "core_ja"), height=100)
    st.text_area("用途キーワード 日本語", key=draft_widget_key(draft_id, "use_ja"), height=80)
    st.text_area("材料・プロセス 日本語", key=draft_widget_key(draft_id, "material_process_ja"), height=80)
    st.text_area("除外キーワード 日本語", key=draft_widget_key(draft_id, "exclude_ja"), height=80)
  with col_right:
    st.text_area("コアキーワード 英語", key=draft_widget_key(draft_id, "core_en"), height=100)
    st.text_area("用途キーワード 英語", key=draft_widget_key(draft_id, "use_en"), height=80)
    st.text_area("材料・プロセス 英語", key=draft_widget_key(draft_id, "material_process_en"), height=80)
    st.text_area("除外キーワード 英語", key=draft_widget_key(draft_id, "exclude_en"), height=80)
  pub_left, pub_right = st.columns(2)
  with pub_left:
    st.text_area("Seed publication numbers", key=draft_widget_key(draft_id, "seed_publications"), height=80)
  with pub_right:
    st.text_area("追加候補 publication numbers", key=draft_widget_key(draft_id, "candidate_publications"), height=80)
  yr_left, yr_right = st.columns(2)
  with yr_left:
    st.text_input("年範囲（開始）", key=draft_widget_key(draft_id, "year_start"))
  with yr_right:
    st.text_input("年範囲（終了）", key=draft_widget_key(draft_id, "year_end"))
  st.text_input("完全一致語", key=draft_widget_key(draft_id, "exact_phrase"))
  st.checkbox("Patent", key=draft_widget_key(draft_id, "enable_patent"))
  st.checkbox("Paper", key=draft_widget_key(draft_id, "enable_paper"))
  st.checkbox("Web", key=draft_widget_key(draft_id, "enable_web"))

  events["save_confirmed"] = st.checkbox(
    "このテーマ案を新しいテーマとして保存します。既存の標準監視テーマは上書きしません。",
    key=f"confirm_save_draft_{draft_id}",
  )
  st.warning("保存内容は勉強会参加者と共有されます。")
  events["discard_confirmed"] = st.checkbox(
    "この未保存テーマ案を破棄します。",
    key=f"confirm_discard_draft_{draft_id}",
  )

  btn1, btn2, btn3 = st.columns(3)
  with btn1:
    events["keep_draft_changes"] = st.button("テーマ案の変更を保持", key=f"btn_keep_draft_{draft_id}")
  with btn2:
    events["save_draft_as_new"] = st.button("新しいテーマとして保存", key=f"btn_save_draft_{draft_id}")
  with btn3:
    events["discard_draft"] = st.button("テーマ案を破棄", key=f"btn_discard_draft_{draft_id}")

  events["draft_editor_payload"] = _read_draft_editor(draft)
  _render_workflow_guide(summary)
  return events


def _render_workflow_guide(summary: Mapping[str, Any]) -> None:
  workflow = dict(summary.get("workflow", {}) or {})
  st.markdown("#### 操作ガイド")
  steps = [
    ("Draft作成", workflow.get("draft_created")),
    ("Draft確認", workflow.get("draft_reviewed")),
    ("Theme保存", workflow.get("theme_saved")),
    ("Watch Profile", workflow.get("watch_profile_generated")),
    ("Search Plan", workflow.get("search_plan_generated")),
    ("Live検索", workflow.get("live_search_executed")),
  ]
  for label, done in steps:
    status = "完了" if done else "未完了"
    st.write(f"- {label}: {status}")


def render_saved_theme_selector(
  *,
  saved_themes: list[Mapping[str, Any]],
  selected_theme_id: str,
) -> dict[str, Any]:
  st.markdown("### 保存済みテーマ一覧")
  if not saved_themes:
    st.info("保存済みテーマはありません。")
    return {"select_theme_id": None}
  options = [str(item.get("theme_id", "")) for item in saved_themes]
  labels = {
    str(item.get("theme_id", "")): (
      f"{item.get('name', '')} | {str(item.get('theme_id', ''))[:12]} | v{item.get('theme_version', 1)} | "
      f"{item.get('status', '')} | {item.get('source', '')}"
    )
    for item in saved_themes
  }
  current_index = options.index(selected_theme_id) if selected_theme_id in options else 0
  chosen = st.selectbox(
    "Themeを選択",
    options=options,
    index=current_index,
    format_func=lambda value: labels.get(str(value), str(value)),
    key="ui_saved_theme_selector",
  )
  load_clicked = st.button("選択したテーマを読み込む", key="btn_load_selected_theme")
  return {"select_theme_id": chosen if load_clicked else None, "selected_preview_id": chosen}


def render_search_plan_preview_with_draft_warning(
  search_plan: Mapping[str, Any] | None,
  *,
  draft: Mapping[str, Any] | None,
  saved_theme: Mapping[str, Any] | None,
) -> None:
  st.markdown("### Search Plan Preview")
  if should_show_old_plan_warning(draft, search_plan, saved_theme):
    st.warning(
      f"以下は保存済み標準監視テーマ『{saved_theme.get('name', DEFAULT_SAVED_THEME_NAME) if saved_theme else DEFAULT_SAVED_THEME_NAME}』"
      "に由来するSearch Planです。現在の未保存サイジング剤テーマ案とは接続されていません。"
    )
    if search_plan:
      summary = build_search_plan_preview_summary(search_plan)
      st.write(f"- Search Plan source theme: `{summary.get('source_theme_id')}` v{summary.get('source_theme_version')}")
      st.write(f"- source Watch Profile: `{summary.get('source_watch_profile_id')}` v{summary.get('source_watch_profile_version')}")
      st.write("- draftとの接続状態: **未接続**")
    if draft and str(draft.get("status", "")) == "draft":
      st.info("Theme draft未保存のため、draft向けWatch Profile / Search Planは生成できません。")
    return
  if not search_plan:
    if draft and str(draft.get("status", "")) == "draft":
      st.info("Theme draft未保存のため、Search Planは未生成です。新しいテーマとして保存後にWatch Profile案を生成してください。")
    else:
      st.info("Search Plan未生成。保存済みWatch Profileから生成してください。")
    return
  summary = build_search_plan_preview_summary(search_plan)
  st.write(f"- Search Plan ID: `{summary.get('search_plan_id')}` v{summary.get('search_plan_version')}")
  st.write(f"- signature: `{summary.get('search_plan_signature_short')}`")
  st.write(f"- 元Theme: `{summary.get('source_theme_id')}` v{summary.get('source_theme_version')}")


def render_standard_theme_actions(*, has_unsaved_draft: bool) -> dict[str, bool]:
  st.markdown("### A. 標準監視テーマ")
  if has_unsaved_draft:
    st.caption("未保存テーマ案（Dセクション）とは別です。下の操作は保存済み標準監視テーマ向けです。")
  col1, col2, col3 = st.columns(3)
  events = {
    "save_theme": False,
    "load_saved_theme": False,
    "generate_watch_profile": False,
    "generate_search_plan": False,
  }
  with col1:
    with st.expander("現在の標準監視テーマを更新保存", expanded=False):
      st.warning("誤操作防止: 更新保存は確認後に実行してください。")
      events["save_theme"] = st.button("標準監視テーマを更新保存", key="btn_theme_update_saved")
  with col2:
    events["generate_watch_profile"] = st.button(
      "標準監視テーマからWatch Profile案を生成",
      key="btn_theme_gen_profile_std",
    )
  with col3:
    events["generate_search_plan"] = st.button(
      "標準監視テーマからSearch Planを生成",
      key="btn_theme_gen_plan_std",
    )
  events["load_saved_theme"] = st.button("保存済みテーマを読み込む", key="btn_theme_load_saved_std")
  return events
