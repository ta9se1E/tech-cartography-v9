"""v8 Gap / Next Actions tab (Phase 27B)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.user_context import resolve_user_context
from tech_cartography.services.live_evidence_gap_builder import load_latest_evidence_gap_artifact
from tech_cartography.services.live_strategic_watch_brief import (
  load_latest_strategic_watch_brief,
  render_strategic_watch_brief_markdown,
)
from tech_cartography.services.live_weekly_decision_cockpit import (
  build_weekly_decision_cockpit_payload,
  load_latest_weekly_decision_cockpit,
)
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box
from tech_cartography.ui.live_evidence_gap_ui import render_live_evidence_gap_section
from tech_cartography.ui.live_strategic_watch_brief_ui import render_live_strategic_watch_brief_section
from tech_cartography.ui.login_ui import can_use_admin_features
from tech_cartography.ui.v8_tab_config import V8_TAB_LABELS


def _top_items(items: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
  return list(items[:limit])


def render_v8_gap_next_actions_tab(*, project_root: Path | str) -> None:
  root = Path(project_root)
  user_context = resolve_user_context()
  is_admin = can_use_admin_features()

  st.markdown("### Gap / Next Actions")
  st.markdown(
    render_caution_box(
      "<strong>候補情報であり確定事実ではありません。</strong> "
      "candidate information only / human review required。"
      " FTO、侵害、有効性判断ではありません。"
      " 外部API・メール送信・Scheduler はこのタブでは実行しません。"
    ),
    unsafe_allow_html=True,
  )

  gap_artifact = load_latest_evidence_gap_artifact(root)
  cockpit_live = build_weekly_decision_cockpit_payload(root, user_context=user_context)
  brief = load_latest_strategic_watch_brief(root)
  cockpit_saved = load_latest_weekly_decision_cockpit(root)

  gaps = _top_items(
    (gap_artifact or {}).get("evidence_gaps")
    or cockpit_live.get("top_evidence_gaps")
    or [],
    limit=3,
  )
  actions = _top_items(
    (gap_artifact or {}).get("next_verification_actions")
    or cockpit_live.get("next_verification_actions")
    or [],
    limit=3,
  )
  what_not = (
    (gap_artifact or {}).get("what_not_to_conclude")
    or cockpit_live.get("what_not_to_conclude")
    or []
  )

  st.markdown("#### Evidence Gap Top 3")
  if gaps:
    st.dataframe(
      pd.DataFrame(
        [
          {
            "gap_id": g.get("gap_id"),
            "urgency": g.get("urgency"),
            "observation": g.get("observation"),
            "support_level": g.get("support_level"),
          }
          for g in gaps
        ],
      ),
      use_container_width=True,
      hide_index=True,
    )
  else:
    st.markdown(render_warning_box("Evidence Gap artifact がありません。管理者が生成すると表示されます。"), unsafe_allow_html=True)

  st.markdown("#### Next Verification Actions（3件）")
  if actions:
    for index, action in enumerate(actions, start=1):
      owner = action.get("recommended_owner") or action.get("owner") or "human review required"
      st.markdown(f"{index}. [{action.get('urgency', '')}] {action.get('action', '')} — {owner}")
  else:
    st.caption("Next Actions は未生成です。")

  st.markdown("#### What Not To Conclude")
  if what_not:
    for item in what_not:
      st.markdown(f"- {item}")
  else:
    st.markdown("- FTO / 侵害 / 有効性 / 法的結論は出しません")
    st.markdown("- Web Signal は candidate information only です")

  st.markdown("#### Source artifact path")
  paths: list[str] = []
  if gap_artifact:
    for path in gap_artifact.get("source_artifact_paths") or []:
      paths.append(str(path))
  for label, path in (cockpit_live.get("latest_artifact_paths") or {}).items():
    if path:
      paths.append(f"{label}: {path}")
  if paths:
    for path in paths:
      st.caption(path)
  else:
    st.caption("artifact path は未保存です。")

  if brief:
    with st.expander("Strategic Watch Brief（閲覧）", expanded=False):
      st.markdown(render_strategic_watch_brief_markdown(brief))

  if cockpit_saved:
    st.caption(f"saved cockpit: {cockpit_saved.get('generated_at')}")

  if is_admin and is_login_required():
    with st.expander("管理者: 生成操作（admin のみ）", expanded=False):
      st.caption("生成は admin のみ。メール・Scheduler・外部APIは実行しません。")
      render_live_evidence_gap_section(project_root=root, key_prefix="v8_gap_admin")
      render_live_strategic_watch_brief_section(project_root=root, key_prefix="v8_brief_admin")
  elif is_login_required():
    st.caption("生成ボタンは管理者のみ利用できます。閲覧は全ログインユーザー向けです。")

  st.markdown(
    render_info_box(f"次は「{V8_TAB_LABELS['fixed_point_observation']}」で定点観測ループを確認してください。"),
    unsafe_allow_html=True,
  )
