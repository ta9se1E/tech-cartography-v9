"""Live Web Signal review UI (Phase 25U)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.services.live_digest_preview import load_latest_live_digest_preview
from tech_cartography.services.live_web_signal_artifact_reader import read_latest_web_signal_artifact_summary
from tech_cartography.services.live_web_signal_review import (
  build_web_signal_review,
  render_web_signal_section_markdown,
)
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box
from tech_cartography.ui.login_ui import can_use_admin_features


def should_show_live_web_signal_review_ui() -> bool:
  return is_login_required() and can_use_admin_features()


def _digest_uses_web_signals(preview: dict[str, Any] | None) -> bool:
  if not preview:
    return False
  if preview.get("uses_web_signals"):
    return True
  return bool(preview.get("source_web_signal_artifact") or preview.get("latest_web_signal_collection_path"))


def render_live_web_signal_review_section(
  *,
  project_root: Path | str,
  key_prefix: str = "live_web_signal_review",
) -> None:
  if not should_show_live_web_signal_review_ui():
    return

  summary = read_latest_web_signal_artifact_summary(project_root)
  review = build_web_signal_review(project_root, source_summary=summary)
  latest_digest = load_latest_live_digest_preview(project_root)
  reflected = _digest_uses_web_signals(latest_digest)

  with st.expander("Web Signal Review（候補情報・Evidence Review）", expanded=False):
    st.markdown(
      render_caution_box(
        "候補情報であり、確定事実ではありません。"
        " FTO、侵害、有効性判断ではありません。"
        " 外部API実行・メール送信・Scheduler起動は行いません。"
      ),
      unsafe_allow_html=True,
    )

    if not summary.get("artifact_exists"):
      st.markdown(render_warning_box("Web Signal候補はまだ収集されていません。"), unsafe_allow_html=True)
    else:
      st.markdown(f"**theme:** {summary.get('theme_name') or '(none)'}")
      st.caption(f"artifact: {summary.get('artifact_path')}")
      st.caption(f"status={summary.get('status')} | result_count={summary.get('result_count')}")

    st.markdown(f"**Digest Preview 反映:** {'済み' if reflected else '未反映'}")
    if reflected and latest_digest:
      st.caption(f"latest digest: {latest_digest.get('created_at')}")

    if review.get("queries_used"):
      st.markdown("**queries_used**")
      for query in review.get("queries_used") or []:
        st.markdown(f"- {query}")

    domain_counts = review.get("signals_by_domain") or {}
    if domain_counts:
      st.markdown("**domain summary**")
      st.dataframe(
        [{"domain": domain, "count": count} for domain, count in domain_counts.items()],
        width="stretch",
        hide_index=True,
      )

    top = review.get("top_candidate_signals") or []
    if top:
      st.markdown("**top candidate signals**")
      st.dataframe(pd.DataFrame(top), width="stretch", hide_index=True)

    for note in review.get("caution_notes") or []:
      st.caption(note)

    st.markdown(render_info_box(str(review.get("candidate_only_notice_ja") or "")), unsafe_allow_html=True)

    if summary.get("artifact_exists"):
      with st.expander("Digest 用 Web Signal section プレビュー", expanded=False):
        st.markdown(render_web_signal_section_markdown(review))
