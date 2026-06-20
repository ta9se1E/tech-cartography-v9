"""Demo-safe UI modes and sidebar (Phase 24.5A)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tech_cartography.ui.easy_japanese_ui import render_info_box, render_warning_box
from tech_cartography.ui.japanese_labels import translate_tab_name
from tech_cartography.ui.streamlit_session import (
  DISPLAY_MODE_OPTIONS,
  STATE_CURRENT_USER,
  STATE_DEMO_MODE,
  STATE_DISPLAY_MODE,
  STATE_MANIFEST_PATH,
  STATE_PENDING_SELECTED_RUN_ID,
  STATE_PIPELINE_ROOT,
  STATE_SELECTED_RUN_ID,
  STATE_UI_MODE,
  WIDGET_DISPLAY_MODE,
  WIDGET_PIPELINE_ROOT,
  WIDGET_SELECTED_RUN_ID,
  WIDGET_UI_MODE,
  activate_evidence_map_demo_state,
  apply_internal_state_updates,
  deactivate_demo_mode_state,
  sync_internal_from_widget_values,
)

UI_MODE_DEMO = "demo"
UI_MODE_ANALYST = "analyst"
UI_MODE_DEVELOPER = "developer"

UI_MODE_OPTIONS: tuple[str, ...] = (UI_MODE_DEMO, UI_MODE_ANALYST, UI_MODE_DEVELOPER)
UI_MODE_LABELS: dict[str, str] = {
  UI_MODE_DEMO: "デモを見る",
  UI_MODE_ANALYST: "本番実行",
  UI_MODE_DEVELOPER: "開発者向け",
}

DEMO_TAB_IDS: tuple[str, ...] = ("start", "evidence", "market", "reports", "settings")
ANALYST_TAB_IDS: tuple[str, ...] = (
  "start",
  "patents",
  "fulltext",
  "evidence",
  "market",
  "theme_validation",
  "reports",
  "settings",
)

USAGE_NOTICE_LINES: tuple[str, ...] = (
  "社外秘・未公開情報を入力しないでください。",
  "外部API実行時は、入力キーワードやクエリが外部サービスに送信される可能性があります。",
  "Paper候補は supporting evidence candidate であり、特許請求項の証明ではありません。",
  "Web Signalは signal candidate です。事実関係や特許との直接関係を断定しません。",
  "Link Candidateは確認候補であり、直接関係の証明ではありません。",
  "Strategic Watchは監視候補であり、最終結論ではありません。",
  "Digestは preview only です。メール送信は行いません。",
  "FTO、侵害、有効性判断、法的見解には使用しません。最終判断には原典確認と専門家レビューが必要です。",
)

SCHEDULER_POST_MVP_NOTICE = (
  "週次スケジューラーの Cloud Scheduler 連携は Post-MVP です。"
  "macOS launchd / cron はローカル検証用であり、Cloud Run 提出画面には表示しません。"
)


def get_ui_mode() -> str:
  import streamlit as st

  mode = str(st.session_state.get(STATE_UI_MODE, UI_MODE_DEMO))
  return mode if mode in UI_MODE_OPTIONS else UI_MODE_DEMO


def is_demo_view() -> bool:
  return get_ui_mode() == UI_MODE_DEMO


def is_analyst_view() -> bool:
  return get_ui_mode() == UI_MODE_ANALYST


def is_developer_view() -> bool:
  return get_ui_mode() == UI_MODE_DEVELOPER


def show_developer_sections() -> bool:
  return is_developer_view()


def apply_ui_mode_side_effects(ui_mode: str) -> dict[str, Any]:
  if ui_mode == UI_MODE_DEMO:
    return activate_evidence_map_demo_state()
  updates = deactivate_demo_mode_state()
  updates[STATE_UI_MODE] = ui_mode
  return updates


def format_display_path(path: Path | str | None, *, project_root: Path | None = None) -> str:
  if not path:
    return "（なし）"
  raw = Path(path)
  try:
    if project_root:
      return raw.relative_to(project_root).as_posix()
  except ValueError:
    pass
  parts = raw.parts
  if "outputs" in parts:
    idx = parts.index("outputs")
    return "/".join(parts[idx:])
  return raw.name


def tab_ids_for_ui_mode(ui_mode: str | None = None) -> tuple[str, ...]:
  mode = ui_mode or get_ui_mode()
  if mode == UI_MODE_DEMO:
    return DEMO_TAB_IDS
  return ANALYST_TAB_IDS


def tab_labels_for_ui_mode(ui_mode: str | None = None) -> list[str]:
  mode = ui_mode or get_ui_mode()
  labels: list[str] = []
  for tab_id in tab_ids_for_ui_mode(mode):
    if tab_id == "theme_validation" and mode in {UI_MODE_ANALYST, UI_MODE_DEVELOPER}:
      labels.append("本番実行")
    else:
      labels.append(translate_tab_name(tab_id))
  return labels


def render_usage_notices_expander(*, expanded: bool = False, key: str = "usage_notices") -> None:
  import streamlit as st

  with st.expander("利用上の注意", expanded=expanded):
    for line in USAGE_NOTICE_LINES:
      st.markdown(f"- {line}")


def render_external_api_consent_note(*, key_prefix: str = "ext_api") -> None:
  import streamlit as st

  st.markdown(
    render_warning_box(
      "外部API実行時は入力キーワードやクエリが外部サービスに送信されます。社外秘情報を含めないでください。"
    ),
    unsafe_allow_html=True,
  )
  st.checkbox(
    "外部API実行に同意します",
    value=False,
    key=f"{key_prefix}_external_api_consent",
  )


def _load_final_validation_next_actions(project_root: Path) -> list[str]:
  path = project_root / "outputs" / "validation" / "final_validation" / "final_end_to_end_validation_summary.json"
  if not path.exists():
    return []
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
  except (json.JSONDecodeError, OSError):
    return []
  actions = data.get("next_actions") or []
  return [str(a) for a in actions if str(a).strip()]


def sidebar_progress_text(ui_mode: str) -> str:
  if ui_mode == UI_MODE_DEMO:
    return "デモ表示中（US-12565719-B2 成果物）"
  if ui_mode == UI_MODE_ANALYST:
    return "本番実行モード（テーマ入力・E2E Chain）"
  return "開発者向けモード（パス・検証サマリー参照可）"


def sidebar_next_steps_text(ui_mode: str, *, project_root: Path) -> str:
  if ui_mode == UI_MODE_DEMO:
    return "はじめる → 技術の裏取り → 企業・市場シグナル → レポート"
  if ui_mode == UI_MODE_ANALYST:
    actions = _load_final_validation_next_actions(project_root)
    if actions:
      return actions[0]
    return "seed status / Final Validation の next_action を確認"
  return "開発者向け expander で run_id・validation paths を確認"


def render_developer_info_expander(
  *,
  project_root: Path,
  pipeline_root: str,
  run_id: str,
  user: dict[str, Any],
  sidebar_button,
  key: str = "developer_info",
) -> None:
  import streamlit as st

  from tech_cartography.orchestration.latest_outputs import read_latest_run_pointer
  from tech_cartography.ui.streamlit_session import (
    STATE_CURRENT_USER,
    STATE_MANIFEST_PATH,
    STATE_PENDING_SELECTED_RUN_ID,
    STATE_PIPELINE_ROOT,
    STATE_SELECTED_RUN_ID,
    WIDGET_PIPELINE_ROOT,
    WIDGET_SELECTED_RUN_ID,
    activate_evidence_map_demo_state,
    deactivate_demo_mode_state,
  )
  from tech_cartography.users.user_store import set_last_run_id

  with st.expander("開発者向け情報", expanded=False):
    st.caption("ローカル開発・検証用。通常ユーザー画面には表示しません。")
    st.markdown(f"- run_id: `{run_id or user.get('last_run_id') or '未選択'}`")
    st.markdown(f"- outputs path: `{format_display_path(pipeline_root, project_root=project_root)}`")
    pointer = read_latest_run_pointer(pipeline_root)
    if pointer and pointer.get("run_id"):
      st.markdown(f"- latest_run: `{pointer['run_id']}`")
    validation_paths = [
      project_root / "outputs" / "validation" / "core_validation",
      project_root / "outputs" / "validation" / "final_validation",
      project_root / "outputs" / "validation" / "end_to_end_chain",
    ]
    st.markdown("- validation paths:")
    for vp in validation_paths:
      if vp.exists():
        st.markdown(f"  - `{format_display_path(vp, project_root=project_root)}`")
    log_dir = project_root / "outputs" / "delivery" / "email_send_logs"
    if log_dir.exists():
      st.markdown(f"- send log dir: `{format_display_path(log_dir, project_root=project_root)}`")
    st.markdown(render_info_box(SCHEDULER_POST_MVP_NOTICE), unsafe_allow_html=True)

    st.divider()
    pipeline_root_input = st.text_input(
      "実行結果フォルダ",
      key=WIDGET_PIPELINE_ROOT,
      help="outputs/pipeline_runs など",
    )
    run_id_input = st.text_input("run_id", key=WIDGET_SELECTED_RUN_ID)
    if run_id_input and str(run_id_input).strip():
      st.session_state[STATE_SELECTED_RUN_ID] = str(run_id_input).strip()

    if sidebar_button("latest_run を読み込む", key="load_latest_run_button"):
      for state_key, value in deactivate_demo_mode_state().items():
        st.session_state[state_key] = value
      pointer = read_latest_run_pointer(pipeline_root_input)
      if pointer and pointer.get("run_id"):
        rid = str(pointer["run_id"])
        st.session_state[STATE_SELECTED_RUN_ID] = rid
        st.session_state[STATE_PENDING_SELECTED_RUN_ID] = rid
        st.session_state[STATE_MANIFEST_PATH] = pointer.get("manifest_path", "")
        updated_user = set_last_run_id(user["user_id"], rid)
        st.session_state[STATE_CURRENT_USER] = updated_user
        st.success(f"最新 run: {rid}")
        st.rerun()
      else:
        st.warning("latest_run.json が見つかりません。")

    if sidebar_button(
      "デモ成果物を読み込む",
      key="load_demo_evidence_map_button",
    ):
      for state_key, value in activate_evidence_map_demo_state().items():
        st.session_state[state_key] = value
      st.success("デモ成果物を読み込みました。")
      st.rerun()


def render_app_sidebar(
  user: dict[str, Any],
  *,
  project_root: Path,
  sidebar_button,
) -> None:
  """Render demo-safe sidebar (called from app.py)."""
  import streamlit as st

  from tech_cartography.orchestration.latest_outputs import read_latest_run_pointer
  from tech_cartography.ui.login_view import render_logged_in_header

  st.header("ユーザー")
  render_logged_in_header(user)
  if user.get("company_name"):
    st.caption(f"会社: {user['company_name']}")
  if sidebar_button("ログアウト", key="logout_button"):
    from tech_cartography.ui.login_view import logout_user

    logout_user()
    st.rerun()

  st.divider()
  st.header("表示モード")

  current_ui_mode = get_ui_mode()
  mode_index = UI_MODE_OPTIONS.index(current_ui_mode) if current_ui_mode in UI_MODE_OPTIONS else 0
  ui_mode_input = st.radio(
    "モード選択",
    list(UI_MODE_OPTIONS),
    index=mode_index,
    format_func=lambda m: UI_MODE_LABELS.get(m, m),
    key=WIDGET_UI_MODE,
  )

  prev_mode = st.session_state.get("_prev_ui_mode", current_ui_mode)
  if ui_mode_input != prev_mode:
    st.session_state["_prev_ui_mode"] = ui_mode_input
    for key, value in apply_ui_mode_side_effects(ui_mode_input).items():
      st.session_state[key] = value
    st.session_state[STATE_UI_MODE] = ui_mode_input
    st.rerun()
  st.session_state[STATE_UI_MODE] = ui_mode_input

  st.markdown("**現在の進捗**")
  st.caption(sidebar_progress_text(ui_mode_input))

  st.markdown("**次にやること**")
  st.caption(sidebar_next_steps_text(ui_mode_input, project_root=project_root))

  if ui_mode_input == UI_MODE_DEVELOPER:
    pipeline_root = str(st.session_state.get(STATE_PIPELINE_ROOT, project_root / "outputs" / "pipeline_runs"))
    run_id = str(st.session_state.get(STATE_SELECTED_RUN_ID, "") or user.get("last_run_id") or "")
    render_developer_info_expander(
      project_root=project_root,
      pipeline_root=pipeline_root,
      run_id=run_id,
      user=user,
      sidebar_button=sidebar_button,
    )

  if ui_mode_input in {UI_MODE_ANALYST, UI_MODE_DEVELOPER}:
    current_mode = st.session_state.get(STATE_DISPLAY_MODE, DISPLAY_MODE_OPTIONS[0])
    mode_index_display = DISPLAY_MODE_OPTIONS.index(current_mode) if current_mode in DISPLAY_MODE_OPTIONS else 0
    display_mode_input = st.radio(
      "表示モード",
      list(DISPLAY_MODE_OPTIONS),
      index=mode_index_display,
      key=WIDGET_DISPLAY_MODE,
    )
    pipeline_root_val = str(st.session_state.get(STATE_PIPELINE_ROOT, ""))
    run_id_val = str(st.session_state.get(STATE_SELECTED_RUN_ID, ""))
    internal_updates = sync_internal_from_widget_values(
      pipeline_root=pipeline_root_val,
      selected_run_id=run_id_val,
      display_mode=display_mode_input,
    )
    for key, value in internal_updates.items():
      st.session_state[key] = value
  else:
    for key, value in apply_ui_mode_side_effects(UI_MODE_DEMO).items():
      if key not in {STATE_UI_MODE}:
        st.session_state[key] = value

  if ui_mode_input == UI_MODE_ANALYST:
    st.markdown(
      render_info_box("本番実行モード: テーマ入力・Manual Claims・E2E Chain を利用できます。"),
      unsafe_allow_html=True,
    )
