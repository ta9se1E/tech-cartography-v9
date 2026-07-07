"""Theme draft review/edit/save-as-new UI for Study Demo."""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from services_v9.study_demo_theme_draft import (
  can_generate_plan_for_draft,
  can_save_draft_as_new,
  draft_widget_key,
  should_show_old_plan_warning,
  summarize_theme_draft_state,
  validate_draft_generation_precondition,
)
from services_v9.study_demo_theme_draft_mapping import validate_theme_name
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
  payload = {
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
  candidates = list(draft.get("term_candidates", []) or [])
  adopted: list[str] = []
  for item in candidates:
    value = str(item.get("value", "") or "")
    if st.session_state.get(draft_widget_key(draft_id, f"adopt_{value}")):
      adopted.append(value)
  payload["adopted_candidates"] = adopted
  payload["review_confirmed"] = bool(st.session_state.get(draft_widget_key(draft_id, "review_confirmed")))
  payload["use_suggested_name"] = bool(st.session_state.get(draft_widget_key(draft_id, "use_suggested_name")))
  return payload


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
    "complete_draft_review": False,
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
  st.markdown("**状態:** 未保存テーマ案")
  st.write(f"- Theme draft ID: `{draft.get('draft_id', '')}`")
  st.write(f"- 保存予定Theme ID: `{draft.get('theme_id', '')}` / version `{draft.get('theme_version', 1)}`")
  st.write("- **作成元:** 一時キーワード検索")
  st.write(f"- **元Search Run:** `{draft.get('source_search_run_id', '')}`")
  st.write(f"- 未保存変更: {'あり' if draft.get('dirty') else 'なし'}")
  st.write("- **既存テーマへの影響:** なし")
  st.write("- **Active Contextへの影響:** なし")
  st.write("- 自動保存: しない / 自動適用: しない")
  review_label = str(summary.get("review_label", "未完了"))
  st.write(f"- Draft確認: **{review_label}**")

  with st.expander("技術情報", expanded=False):
    st.write(f"- Theme内容シグネチャ: `{str(draft.get('theme_signature', ''))[:8]}`")
    st.write(f"- Draft状態シグネチャ: `{summary.get('theme_draft_signature_short', '')}`")
    st.write(f"- context generation: `{draft.get('created_from_context_generation', '')}`")
    st.write(f"- source request ref: `{draft.get('original_search_request_ref', '')}`")

  _ensure_draft_widget_defaults(draft)
  draft_id = str(draft.get("draft_id", "") or "")
  suggested = str(draft.get("suggested_theme_name", "") or "")
  if suggested:
    st.markdown("#### 推奨テーマ名")
    st.caption(f"元の検索テーマ文: {draft.get('original_active_theme_text', '')}")
    st.write(f"推奨: **{suggested}**")
    st.checkbox("推奨テーマ名を使う", key=draft_widget_key(draft_id, "use_suggested_name"), value=True)
  for issue in validate_theme_name(str(draft.get("name", "")), description=str(draft.get("description", ""))):
    if issue.get("severity") == "warning":
      st.warning(str(issue.get("message", "")))

  st.markdown("#### テーマ案の編集")
  st.text_input("テーマ名", key=draft_widget_key(draft_id, "name"))
  st.text_area("テーマ説明", key=draft_widget_key(draft_id, "description"), height=120)
  col_left, col_right = st.columns(2)
  with col_left:
    st.text_area("コアキーワード 日本語", key=draft_widget_key(draft_id, "core_ja"), height=100)
    st.text_area("用途・評価キーワード 日本語", key=draft_widget_key(draft_id, "use_ja"), height=80)
    st.text_area("材料・プロセス 日本語", key=draft_widget_key(draft_id, "material_process_ja"), height=80)
    st.text_area("除外キーワード 日本語", key=draft_widget_key(draft_id, "exclude_ja"), height=80)
  with col_right:
    st.text_area("コアキーワード 英語", key=draft_widget_key(draft_id, "core_en"), height=100)
    st.text_area("用途・評価キーワード 英語", key=draft_widget_key(draft_id, "use_en"), height=80)
    st.text_area("材料・プロセス 英語", key=draft_widget_key(draft_id, "material_process_en"), height=80)
    st.text_area("除外キーワード 英語", key=draft_widget_key(draft_id, "exclude_en"), height=80)

  _render_mapping_review(draft)
  _render_term_candidates(draft)

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

  st.checkbox(
    "テーマ案の内容とキーワード分類を確認しました",
    key=draft_widget_key(draft_id, "review_confirmed"),
  )
  events["complete_draft_review"] = st.button("テーマ案の確認を完了", key=f"btn_complete_review_{draft_id}")
  if str(draft.get("review_status", "")) != "reviewed":
    st.caption("Draft確認が完了するまで新規保存できません。")

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
    save_disabled = not can_save_draft_as_new(draft)
    events["save_draft_as_new"] = st.button(
      "新しいテーマとして保存",
      key=f"btn_save_draft_{draft_id}",
      disabled=save_disabled,
    )
  with btn3:
    events["discard_draft"] = st.button("テーマ案を破棄", key=f"btn_discard_draft_{draft_id}")

  events["draft_editor_payload"] = _read_draft_editor(draft)
  _render_workflow_guide(summary)
  return events


def _render_mapping_review(draft: Mapping[str, Any]) -> None:
  terms = list(draft.get("mapping_terms", []) or [])
  if not terms:
    return
  explicit_excludes = [
    item
    for item in terms
    if str(item.get("semantic_bucket", "")) == "exclude"
    and str(item.get("provenance", "")) == "explicit_request_field"
    and item.get("accepted_for_theme")
  ]
  if explicit_excludes:
    st.caption("確定済み英語除外語（一時検索で明示）")
    for item in explicit_excludes:
      st.write(f"- {item.get('value')} — 確定済み / 一時検索で明示")
  with st.expander("キーワード分類確認", expanded=False):
    accepted = [item for item in terms if item.get("accepted_for_theme")]
    st.caption("確定語")
    for item in accepted[:12]:
      if item in explicit_excludes:
        continue
      st.write(
        f"- {item.get('value')} | {item.get('language')} | {item.get('semantic_bucket')} | "
        f"{item.get('provenance')} | 確定"
      )
    pending = [item for item in terms if item.get("requires_user_review")]
    if pending:
      st.caption("要確認")
      for item in pending[:8]:
        st.write(f"- {item.get('value')} | 候補 | {item.get('provenance')}")


def _render_term_candidates(draft: Mapping[str, Any]) -> None:
  explicit_exclude_values = {
    str(item.get("value", "") or "").lower()
    for item in list(draft.get("mapping_terms", []) or [])
    if str(item.get("semantic_bucket", "")) == "exclude"
    and str(item.get("provenance", "")) == "explicit_request_field"
    and item.get("accepted_for_theme")
  }
  candidates = [
    item
    for item in list(draft.get("term_candidates", []) or [])
    if str(item.get("value", "") or "").lower() not in explicit_exclude_values
  ]
  if not candidates:
    return
  draft_id = str(draft.get("draft_id", "") or "")
  st.markdown("#### テーマ文から抽出した候補 / 英語alias候補")
  st.caption("候補語は内容確認後に採用してください。")
  for item in candidates:
    value = str(item.get("value", "") or "")
    label = (
      f"{value} ({item.get('language')}, {item.get('semantic_bucket')}) "
      f"— 確認が必要 [{item.get('provenance')}]"
    )
    st.checkbox(label, key=draft_widget_key(draft_id, f"adopt_{value}"))


def _render_workflow_guide(summary: Mapping[str, Any]) -> None:
  workflow = dict(summary.get("workflow", {}) or {})
  st.markdown("#### 操作ガイド")
  review_label = str(workflow.get("draft_review_label", "未完了"))
  steps = [
    ("Draft作成", workflow.get("draft_created")),
    (f"Draft確認 ({review_label})", workflow.get("draft_reviewed")),
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
  show_technical_ids: bool = True,
) -> dict[str, Any]:
  st.markdown("### 保存済みテーマ一覧")
  if not saved_themes:
    st.info("保存済みテーマはありません。")
    return {"select_theme_id": None}
  options = [str(item.get("theme_id", "")) for item in saved_themes]
  if show_technical_ids:
    labels = {
      str(item.get("theme_id", "")): (
        f"{item.get('name', '')} | {str(item.get('theme_id', ''))[:12]} | v{item.get('theme_version', 1)} | "
        f"{item.get('status', '')} | {item.get('source', '')}"
      )
      for item in saved_themes
    }
  else:
    labels = {str(item.get("theme_id", "")): str(item.get("name", "") or item.get("theme_id", "")) for item in saved_themes}
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
  profile_summary: Mapping[str, Any] | None = None,
  search_plan_state: Mapping[str, Any] | None = None,
  active_context: Mapping[str, Any] | None = None,
  lineage_status: Mapping[str, Any] | None = None,
) -> None:
  if should_show_old_plan_warning(draft, search_plan, saved_theme):
    theme_name = str((saved_theme or {}).get("name", DEFAULT_SAVED_THEME_NAME))
    st.markdown("### Search Plan Preview")
    st.warning(
      f"保存済み標準テーマ『{theme_name}』に由来する旧Search Planです。"
      "現在の未保存テーマ案とは**未接続**です。このPlanはdraft用検索には使用されません。"
    )
    if draft:
      st.write(f"- Current draft ID: `{draft.get('draft_id', '')}`")
    st.write("- 接続状態: **未接続**")
    with st.expander("保存済み標準テーマ由来の旧Search Plan（現在のTheme draftとは未接続）", expanded=False):
      if search_plan:
        summary = build_search_plan_preview_summary(search_plan)
        st.write(f"- Plan source theme: `{summary.get('source_theme_id')}` v{summary.get('source_theme_version')}")
        st.write(f"- source Watch Profile: `{summary.get('source_watch_profile_id')}` v{summary.get('source_watch_profile_version')}")
        st.write(f"- source Search Plan: `{summary.get('search_plan_id')}` v{summary.get('search_plan_version')}")
        st.write(f"- signature: `{summary.get('search_plan_signature_short')}`")
      if search_plan_state:
        st.write(
          f"- Watch Profile signature一致: "
          f"{'有効' if not bool(search_plan_state.get('profile_signature_changed', False)) else '不一致'}"
        )
        if search_plan_state.get("stale"):
          st.warning("保存済み標準テーマについて、Search Planが最新Watch Profileをまだ反映していません。")
        else:
          st.success(
            f"保存済み標準テーマ『{theme_name}』については、Search Planが最新です。"
            "現在の未保存Theme draftには適用されません。"
          )
      if draft and str(draft.get("status", "")) == "draft":
        st.info("Theme draft未保存のため、draft向けWatch Profile / Search Planは生成できません。")
    return

  st.markdown("### Search Plan Preview")
  if not search_plan:
    if draft and str(draft.get("status", "")) == "draft":
      st.info("Theme draft未保存のため、Search Planは未生成です。新しいテーマとして保存後にWatch Profile案を生成してください。")
    else:
      st.info("Search Plan未生成。保存済みWatch Profileから生成してください。")
    return
  summary = build_search_plan_preview_summary(search_plan)
  status = dict(lineage_status or {})
  connected = str(status.get("lineage_status", "")) == "connected"
  st.write(f"- Search Plan ID: `{summary.get('search_plan_id')}` v{summary.get('search_plan_version')}")
  st.write(f"- signature: `{summary.get('search_plan_signature_short')}`")
  st.write(f"- 元Theme: `{summary.get('source_theme_id')}` v{summary.get('source_theme_version')}")
  st.write(f"- source Watch Profile: `{summary.get('source_watch_profile_id')}` v{summary.get('source_watch_profile_version')}")
  st.write(f"- validation_status: `{summary.get('validation_status', '—')}`")
  limits = dict(summary.get("provider_limits", {}) or {})
  st.write(
    f"- provider limits: Patent {limits.get('patent', '—')} / Paper {limits.get('paper', '—')} / Web {limits.get('web', '—')}"
  )
  if summary.get("patent_query_summary"):
    st.write(f"- patent query: {summary.get('patent_query_summary')}")
  if summary.get("paper_query_summary"):
    st.write(f"- paper query: {summary.get('paper_query_summary')}")
  if summary.get("web_query_summary"):
    st.write(f"- web query: {summary.get('web_query_summary')}")
  excludes = list(summary.get("exclude_keywords", []) or [])
  if excludes:
    st.write(f"- exclusions: {', '.join(str(item) for item in excludes[:8])}")
  if connected:
    st.write("- lineage_status: **connected**")
  elif active_context:
    st.write(f"- lineage_status: `{status.get('lineage_status', active_context.get('lineage_status', '—'))}`")


def render_standard_theme_actions(*, has_unsaved_draft: bool) -> dict[str, bool]:
  st.markdown("### A. 標準監視テーマ")
  if has_unsaved_draft:
    st.caption("未保存テーマ案（Dセクション）とは別です。下の操作は保存済み標準監視テーマ向けです。")
  events = {
    "save_theme": False,
    "load_saved_theme": False,
    "generate_watch_profile": False,
    "generate_search_plan": False,
  }
  if has_unsaved_draft:
    with st.expander("保存済み標準監視テーマの操作（未保存テーマ案には影響しません）", expanded=False):
      st.warning("これらの操作は旧標準テーマ向けです。未保存Theme draftには適用されません。")
      events["save_theme"] = st.button("標準監視テーマを更新保存", key="btn_theme_update_saved")
      events["generate_watch_profile"] = st.button(
        "標準監視テーマからWatch Profile案を生成",
        key="btn_theme_gen_profile_std",
      )
      events["generate_search_plan"] = st.button(
        "標準監視テーマからSearch Planを生成",
        key="btn_theme_gen_plan_std",
      )
      events["load_saved_theme"] = st.button("保存済みテーマを読み込む", key="btn_theme_load_saved_std")
  else:
    col1, col2, col3 = st.columns(3)
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


def render_legacy_search_plan_controls(
  *,
  has_unsaved_draft: bool,
  profile_status_message: str | None,
  search_plan_status_message: str | None,
  search_plan_state: Mapping[str, Any],
  profile_summary: Mapping[str, Any],
  saved_theme_name: str,
) -> dict[str, bool]:
  """Watch profile / search plan controls scoped away from draft when draft exists."""
  events = {
    "save_profile": False,
    "load_profile": False,
    "regenerate_search_plan": False,
  }
  if has_unsaved_draft:
    with st.expander("保存済み標準テーマ由来の監視プロファイル操作（draft未接続）", expanded=False):
      st.warning("未保存Theme draftには影響しません。旧標準テーマ向けの操作です。")
      col1, col2, col3 = st.columns(3)
      with col1:
        events["save_profile"] = st.button("監視プロファイルを保存", key="btn_theme_save_profile", width="stretch")
      with col2:
        events["load_profile"] = st.button("保存済み監視プロファイルを読み込む", key="btn_theme_load_profile", width="stretch")
      with col3:
        events["regenerate_search_plan"] = st.button("検索計画を再生成", key="btn_theme_regenerate_search_plan", width="stretch")
      if profile_status_message:
        st.caption(profile_status_message)
      if search_plan_status_message:
        st.caption(search_plan_status_message)
      st.markdown("#### 旧Search Plan状態")
      st.write(f"- 最終生成: {search_plan_state.get('generated_at', '未生成')}")
      st.write(
        f"- Watch Profile signature一致: "
        f"{'有効' if not bool(search_plan_state.get('profile_signature_changed', False)) else '不一致'}"
      )
      if search_plan_state.get("stale"):
        st.warning("保存済み標準テーマについて、Search Planが最新Watch Profileをまだ反映していません。")
      else:
        st.success(
          f"保存済み標準テーマ『{saved_theme_name}』については、Search Planが最新です。"
          "現在の未保存Theme draftには適用されません。"
        )
    return events

  col1, col2, col3 = st.columns(3)
  with col1:
    events["save_profile"] = st.button("監視プロファイルを保存", key="btn_theme_save_profile", width="stretch")
  with col2:
    events["load_profile"] = st.button("保存済み監視プロファイルを読み込む", key="btn_theme_load_profile", width="stretch")
  with col3:
    events["regenerate_search_plan"] = st.button("検索計画を再生成", key="btn_theme_regenerate_search_plan", width="stretch")
  return events
