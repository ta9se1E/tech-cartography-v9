"""Tab renderers for the lightweight Tech Cartography v9 UI."""

from __future__ import annotations

import json
from typing import Sequence

import streamlit as st

from services_v9.signal_models import Signal, WatchProfile
from services_v9.signal_scoring import (
  build_diversity_counts,
  compute_theme_drift_alert,
  format_score_delta,
  select_diverse_top_signals,
  select_top_reads,
  summarize_status_buckets,
)

V9_TAB_LABELS = [
  "Theme Setup",
  "Sources",
  "Top Signals",
  "Weekly Updates",
  "Watch Profile",
  "Digest / Export",
]

FORBIDDEN_UI_LABELS = [
  "PDF Deep Dive",
  "Google Vision OCR",
  "PDF Upload",
  "Claim Map",
  "Evidence Map",
  "Gap",
  "Strategic Brief",
  "Pipeline Doctor",
  "Publication Identity Guard",
  "Quarantine",
]

NOTICE_EN = (
  "v9 is a lightweight R&D signal watch preview. "
  "It does not perform PDF/OCR deep dive, claim interpretation, legal judgment, "
  "FTO judgment, infringement judgment, patentability judgment, or technical validation."
)
NOTICE_JA = (
  "v9は軽量なR&Dシグナル監視プレビューです。"
  "PDF/OCR深掘り、クレーム解釈、法的判断、FTO判断、侵害判断、特許性判断、"
  "技術的妥当性の証明は行いません。"
)


def render_notice() -> None:
  st.info(f"{NOTICE_EN}\n\n{NOTICE_JA}")


def render_theme_setup_tab(watch_profile: WatchProfile) -> None:
  st.subheader("Tech Cartography v9")
  st.caption("Lightweight R&D Signal Watch Agent")

  left, right = st.columns([2, 1])
  with left:
    st.text_area("Research Theme", key="v9_theme", height=100)
    st.text_input("Monitoring Goal", key="v9_watch_goal")
  with right:
    st.checkbox("Demo Mode", key="v9_demo_mode")
    st.markdown("**External APIs:** OFF")
    st.markdown("**Runtime mode:** local demo data only")
    st.markdown("**Email / Scheduler:** Preview only / OFF")

  st.caption(
    "Initial theme example: PAN系炭素繊維のサイジング、表面処理、界面接着、"
    "ストランド引張弾性率"
  )
  st.write("Current watch cadence:", watch_profile.cadence)


def render_sources_tab(source_rows: Sequence[dict[str, object]], operation_rows: Sequence[str]) -> None:
  st.subheader("Sources")
  st.caption("Patent / Paper / Web / Company are shown as lightweight local or staged preview sources only.")

  for row in source_rows:
    st.markdown(
      f"- **{row['source_type']}** | enabled: `{row['enabled']}` | mode: `{row['mode']}` | "
      f"TopN: `{row['top_n']}` | last updated: `{row['last_updated']}` | note: {row['note']}"
    )

  st.markdown("### Operation Status")
  for item in operation_rows:
    st.write(f"- {item}")


def render_top_signals_tab(signals: Sequence[Signal]) -> None:
  st.subheader("Top Signals")
  top_signals = select_diverse_top_signals(signals, top_n=10, max_per_type=4)
  top_reads = select_top_reads(top_signals, limit=3)
  diversity_counts = build_diversity_counts(signals)

  st.markdown("### 今週読むべき3件 / This Week's Top 3 Reads")
  if not top_reads:
    st.info("Top read candidates are not available yet.")
  else:
    columns = st.columns(len(top_reads))
    for column, signal in zip(columns, top_reads):
      with column:
        st.markdown(f"**{signal.title}**")
        st.caption(f"{signal.type} | score {signal.score:.2f} | {signal.status} | {signal.action}")
        st.write(signal.why_read)
        st.write(f"次の確認: {signal.what_to_check}")
        st.write(f"次アクション: {signal.next_action}")
        st.markdown(f"[Source URL]({signal.source_url})")

  available_types = sorted({signal.type for signal in top_signals})
  available_statuses = ["New", "Rising", "Dropped", "Stable"]
  available_actions = ["Read Now", "Watch", "Ignore"]

  filter_left, filter_mid, filter_right = st.columns(3)
  with filter_left:
    selected_types = st.multiselect("Type filter", available_types, default=available_types)
  with filter_mid:
    selected_statuses = st.multiselect("Status filter", available_statuses, default=available_statuses)
  with filter_right:
    selected_actions = st.multiselect("Action filter", available_actions, default=available_actions)

  filtered = [
    signal for signal in top_signals
    if signal.type in selected_types and signal.status in selected_statuses and signal.action in selected_actions
  ]

  diversity_text = ", ".join(f"{signal_type}: {count}" for signal_type, count in diversity_counts.items())
  st.caption(f"Diversity Control: {diversity_text} (same type capped at 4 in Top 10)")
  st.caption("Top 10 is score-sorted after lightweight diversity balancing.")

  if not filtered:
    st.warning("No signals match the current filters.")
    return

  for index, signal in enumerate(filtered, start=1):
    st.markdown(f"#### {index}. {signal.title}")
    st.caption(
      f"type: {signal.type} | score: {signal.score:.2f} | status: {signal.status} | "
      f"action: {signal.action} | published: {signal.published_date}"
    )
    st.write(f"**Why read:** {signal.why_read}")
    st.write(f"**What to check:** {signal.what_to_check}")
    st.write(f"**Next action:** {signal.next_action}")
    st.write(f"**Source:** {signal.source_name}")
    st.write(f"**Tags:** {', '.join(signal.tags) if signal.tags else 'n/a'}")
    st.write(f"**Companies:** {', '.join(signal.companies) if signal.companies else 'n/a'}")
    st.markdown(f"[Open source URL]({signal.source_url})")


def render_weekly_updates_tab(signals: Sequence[Signal], watch_profile: WatchProfile) -> None:
  st.subheader("Weekly Updates")
  buckets = summarize_status_buckets(signals)
  metrics = st.columns(4)
  for column, status in zip(metrics, ("New", "Rising", "Dropped", "Stable")):
    column.metric(status, len(buckets[status]))

  st.markdown("### Difference Summary")
  for status in ("New", "Rising", "Dropped", "Stable"):
    items = buckets[status]
    if not items:
      st.write(f"- **{status}**: 0 items")
      continue
    lead = items[0]
    st.write(f"- **{status}**: {len(items)} items | representative signal: {lead.title} | {format_score_delta(lead)}")

  drift = compute_theme_drift_alert(signals, watch_profile)
  st.markdown("### Theme Drift Alert")
  if drift["level"] == "warning":
    st.warning(str(drift["message"]))
  elif drift["level"] == "success":
    st.success(str(drift["message"]))
  else:
    st.info(str(drift["message"]))
  if drift["examples"]:
    st.caption("Low-overlap examples: " + ", ".join(str(item) for item in drift["examples"]))


def render_watch_profile_tab(watch_profile: WatchProfile, suggestions: Sequence[str]) -> None:
  st.subheader("Watch Profile")
  st.write(f"**theme:** {watch_profile.theme}")
  st.write(f"**include keywords:** {', '.join(watch_profile.include_keywords)}")
  st.write(f"**exclude keywords:** {', '.join(watch_profile.exclude_keywords) if watch_profile.exclude_keywords else 'n/a'}")
  st.write(f"**target companies:** {', '.join(watch_profile.target_companies) if watch_profile.target_companies else 'n/a'}")
  st.write(f"**source types:** {', '.join(watch_profile.source_types)}")
  st.write(f"**countries:** {', '.join(watch_profile.countries) if watch_profile.countries else 'n/a'}")
  st.write(f"**cadence:** {watch_profile.cadence}")
  st.write(f"**priority rules:** {', '.join(watch_profile.priority_rules) if watch_profile.priority_rules else 'n/a'}")

  st.markdown("### Suggested Watch Profile Updates")
  for suggestion in suggestions:
    st.write(f"- {suggestion}")

  st.caption("v9-0 では保存処理は未実装です。Export JSON から共有できます。")
  st.code(json.dumps(watch_profile.to_dict(), ensure_ascii=False, indent=2), language="json")


def render_digest_export_tab(
  markdown_text: str,
  csv_text: str,
  json_text: str,
) -> None:
  st.subheader("Digest / Export")
  st.caption("Email delivery: Preview only / OFF")
  st.markdown(markdown_text)

  button_left, button_mid, button_right = st.columns(3)
  with button_left:
    st.download_button(
      "Download Markdown",
      data=markdown_text,
      file_name="tech_cartography_v9_weekly_digest.md",
      mime="text/markdown",
      use_container_width=True,
    )
  with button_mid:
    st.download_button(
      "Download CSV",
      data=csv_text,
      file_name="tech_cartography_v9_top_signals.csv",
      mime="text/csv",
      use_container_width=True,
    )
  with button_right:
    st.download_button(
      "Download JSON",
      data=json_text,
      file_name="tech_cartography_v9_signal_watch.json",
      mime="application/json",
      use_container_width=True,
    )
