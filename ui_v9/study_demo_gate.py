"""Streamlit authentication gate and banner for the v9 study demo service."""

from __future__ import annotations

import streamlit as st

from services_v9.study_demo_access import (
  DEMO_ACTIVE_RUN_ID,
  DEMO_SOURCE_COUNTS,
  DEMO_THEME_NAME,
  DEMO_TIER_COUNTS,
  PUBLIC_DEMO_BADGE,
  PUBLIC_DEMO_LEGAL_CAVEAT,
  PUBLIC_DEMO_SEEDED_NOTICE,
  is_public_demo,
)
from services_v9.study_demo_auth import (
  EXPIRED_MESSAGE,
  FAILURE_MESSAGE,
  NOT_CONFIGURED_MESSAGE,
  SESSION_AUTHENTICATED_KEY,
  SESSION_PASSWORD_INPUT_KEY,
  StudyDemoExpiredError,
  StudyDemoNotConfiguredError,
  clear_authentication,
  cooldown_remaining_seconds,
  ensure_study_demo_access_allowed,
  format_expiry_jst,
  is_authenticated,
  register_failed_attempt,
  register_successful_login,
  verify_password,
)
from services_v9.study_demo_config import is_study_demo_mode, is_study_demo_shared_state


def render_study_demo_login_screen(*, environ: dict[str, str] | None = None) -> bool:
  """Render the password gate. Returns True when the session is authenticated."""
  if not is_study_demo_mode(environ):
    return True

  try:
    ensure_study_demo_access_allowed(environ=environ)
  except StudyDemoExpiredError:
    st.error(EXPIRED_MESSAGE)
    clear_authentication(st.session_state)
    return False
  except StudyDemoNotConfiguredError:
    st.error(NOT_CONFIGURED_MESSAGE)
    clear_authentication(st.session_state)
    return False

  if is_public_demo(environ):
    return True

  if is_authenticated(st.session_state, environ=environ):
    return True

  st.title("Tech Cartography v9")
  st.subheader("勉強会用デモ環境")
  st.caption("共通パスワードでログインしてください。")

  remaining = cooldown_remaining_seconds(st.session_state)
  if remaining > 0:
    st.warning(f"しばらく待ってから再試行してください（残り {remaining:.0f} 秒）。")
    st.stop()

  password = st.text_input("共通パスワード", type="password", key=SESSION_PASSWORD_INPUT_KEY)
  if st.button("ログイン", type="primary"):
    if verify_password(password, environ=environ):
      register_successful_login(st.session_state)
      st.rerun()
    register_failed_attempt(st.session_state)
    st.error(FAILURE_MESSAGE)
  st.stop()
  return False


def render_public_demo_banner(*, environ: dict[str, str] | None = None) -> None:
  if not is_public_demo(environ):
    return
  st.caption(PUBLIC_DEMO_BADGE)
  st.info(
    "\n".join(
      [
        f"**{PUBLIC_DEMO_BADGE}**",
        "",
        PUBLIC_DEMO_SEEDED_NOTICE,
        "",
        f"**Theme:** {DEMO_THEME_NAME}",
        f"**Active run:** seeded validated study data ({DEMO_ACTIVE_RUN_ID[:8]}…)",
        (
          "**Sources:** "
          f"Patent {DEMO_SOURCE_COUNTS['patent']} / "
          f"Paper {DEMO_SOURCE_COUNTS['paper']} / "
          f"Web {DEMO_SOURCE_COUNTS['web']} "
          f"(integrated {DEMO_SOURCE_COUNTS['integrated']})"
        ),
        (
          "**Tier mix:** "
          f"A {DEMO_TIER_COUNTS['A']} / "
          f"B {DEMO_TIER_COUNTS['B']} / "
          f"C {DEMO_TIER_COUNTS['C']} / "
          f"D {DEMO_TIER_COUNTS['D']}"
        ),
        "",
        PUBLIC_DEMO_LEGAL_CAVEAT,
      ]
    )
  )


def render_study_demo_banner(*, environ: dict[str, str] | None = None) -> None:
  if is_public_demo(environ):
    render_public_demo_banner(environ=environ)
    return
  if not is_study_demo_mode(environ):
    return
  expiry_text = format_expiry_jst(environ=environ)
  st.info(
    "\n".join(
      [
        "**勉強会用デモ環境**",
        "",
        "・保存済み実データを使用しています",
        "・変更内容は参加者全員に共有されます" if is_study_demo_shared_state(environ) else "・共有状態設定を確認してください",
        "・一時キーワード検索: Patent / Paper / Web 有効",
        "・ページ表示・履歴表示: 外部APIを実行しない",
        "・自動週次実行: 停止中",
        "・メール送信: 停止中",
        "・本番環境: 変更しない",
        f"・公開終了日時: {expiry_text}",
      ]
    )
  )
  if st.button("ログアウト", key="v9_study_demo_logout_button"):
    clear_authentication(st.session_state)
    st.session_state.pop(SESSION_AUTHENTICATED_KEY, None)
    st.rerun()


__all__ = [
  "render_public_demo_banner",
  "render_study_demo_banner",
  "render_study_demo_login_screen",
]
