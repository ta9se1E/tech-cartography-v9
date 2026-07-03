"""Tech Cartography v9 lightweight entry point."""

from ui_v9.signal_watch_app import run_app

# Legacy reference only. The v8/v7 runtime has been moved to `app_v8_legacy.py`
# so `app.py` can stay lightweight for v9-0 startup.
# APP_UI_VERSION
# DEFAULT_UI_VERSION = "v8"
# if is_login_required():
#   auth_session = require_auth_login_gate()
#   user = build_app_user_from_auth_session(auth_session or {})
# else:
#   user = require_login()
# render_app_sidebar
# apply_pending_widget_state_updates()
# def _sidebar_button(label: str, **kwargs: Any) -> bool:
#   return st.button(label, width="stretch", **kwargs)
# from tech_cartography.ui.v7_easy_app import DEFAULT_PIPELINE_ROOT, PROJECT_ROOT, render_tabbed_easy_app
# from tech_cartography.ui.v8_user_flow_app import DEFAULT_PIPELINE_ROOT, PROJECT_ROOT, render_v8_user_flow_app
# init_app_session_state(user)


if __name__ == "__main__":
  run_app()
