"""Strategic Watch Brief UI — load brief outputs and render Streamlit sections (Phase 23.5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.strategic_watch.brief_builder import safe_read_csv, safe_read_text
from tech_cartography.strategic_watch.schema import BRIEF_CAUTION, WATCH_PRIORITY_NOTE
from tech_cartography.ui.easy_japanese_ui import (
  render_caution_box,
  render_dataframe_stretch,
  render_info_box,
  render_markdown_preview,
  render_metric_cards,
  render_warning_box,
)

NOT_AVAILABLE = "not available"
DEFAULT_BRIEF_PUB = "US-12565719-B2"
STRATEGIC_WATCH_RELATIVE_DIR = "outputs/strategic_watch_briefs"

ARTIFACT_FILES: dict[str, str] = {
  "brief_json": "strategic_watch_brief.json",
  "items_csv": "strategic_watch_items.csv",
  "top_items_csv": "top_strategic_watch_items.csv",
  "brief_md": "strategic_watch_brief.md",
  "next_actions_md": "strategic_watch_next_actions.md",
}

STRATEGIC_WATCH_CAUTION_JA = (
  "Strategic Watch Briefは、最終結論ではなく重点監視候補です。"
  "特許・論文・Web情報の重なりをもとに、次に確認すべきテーマを整理します。"
  "FTO、侵害、有効性判断ではありません。"
  "Web signals are signal candidates, not final conclusions. "
  "Papers are supporting evidence candidates, not proof of patent claims."
)

MISSING_ARTIFACT_WARNING = (
  "Strategic Watch Brief の成果物が見つかりません。"
  "先に scripts/build_strategic_watch_brief.py を実行してください。"
)

TOP_WATCH_COLUMNS: tuple[str, ...] = (
  "watch_theme",
  "watch_type",
  "watch_priority",
  "related_paper_title",
  "related_web_signal_title",
  "related_web_signal_domain",
  "source_quality",
  "link_score",
  "link_confidence",
  "why_it_matters",
  "next_verification_action",
  "related_web_signal_url",
)

NATIONAL_MONEY_TYPES: frozenset[str] = frozenset({"national_project_signal", "money_signal"})
IR_TYPES: frozenset[str] = frozenset({"ir_disclosure_signal"})
PATENT_PAPER_WEB_TYPES: frozenset[str] = frozenset({"patent_paper_web_signal"})


@dataclass
class StrategicWatchUIArtifacts:
  publication_number: str
  status: str
  brief_dir: str
  watch_items_df: pd.DataFrame = field(default_factory=pd.DataFrame)
  top_watch_items_df: pd.DataFrame = field(default_factory=pd.DataFrame)
  brief_md: str | None = None
  next_actions_md: str | None = None
  missing_artifacts: list[str] = field(default_factory=list)
  errors: list[str] = field(default_factory=list)


def _brief_dir_for_pub(project_root: Path, publication_number: str | None = None) -> Path:
  pub = publication_number or DEFAULT_BRIEF_PUB
  return project_root / STRATEGIC_WATCH_RELATIVE_DIR / pub


def _compute_loader_status(missing: list[str], items_df: pd.DataFrame) -> str:
  if len(missing) >= len(ARTIFACT_FILES):
    return "missing"
  if missing:
    return "partial"
  if items_df.empty:
    return "partial"
  return "ready"


def normalize_display_value(value: Any, *, max_len: int = 200) -> str:
  if value is None:
    return NOT_AVAILABLE
  if isinstance(value, float) and pd.isna(value):
    return NOT_AVAILABLE
  if pd.isna(value):
    return NOT_AVAILABLE
  text = str(value).strip()
  if not text or text.lower() in {"nan", "none", "nat"}:
    return NOT_AVAILABLE
  if len(text) > max_len:
    return text[: max_len - 1] + "…"
  return text


def prepare_strategic_watch_display_df(
  df: pd.DataFrame,
  columns: tuple[str, ...] | None = None,
) -> pd.DataFrame:
  if df is None or df.empty:
    return pd.DataFrame()

  out = df.copy()
  for col in out.columns:
    out[col] = out[col].apply(lambda v: normalize_display_value(v))

  if columns:
    present = [col for col in columns if col in out.columns]
    out = out[present]

  if "related_web_signal_url" in out.columns:
    out["related_web_signal_url"] = out["related_web_signal_url"].apply(_format_url_link)

  return out


def _format_url_link(value: str) -> str:
  text = str(value).strip()
  if not text or text == NOT_AVAILABLE:
    return NOT_AVAILABLE
  if text.startswith("http"):
    return text
  return text


def get_strategic_watch_status_counts(artifacts: StrategicWatchUIArtifacts) -> dict[str, int]:
  df = artifacts.watch_items_df
  if df.empty:
    return {
      "watch_items": 0,
      "top_watch_items": 0,
      "high_priority": 0,
      "medium_priority": 0,
      "low_priority": 0,
      "national_project_money": 0,
      "ir_disclosure": 0,
    }

  def _count_priority(value: str) -> int:
    if "watch_priority" not in df.columns:
      return 0
    return int((df["watch_priority"].astype(str).str.lower() == value).sum())

  def _count_type(types: frozenset[str]) -> int:
    if "watch_type" not in df.columns:
      return 0
    return int(df["watch_type"].astype(str).isin(types).sum())

  top_count = len(artifacts.top_watch_items_df) if not artifacts.top_watch_items_df.empty else 0
  return {
    "watch_items": len(df),
    "top_watch_items": top_count,
    "high_priority": _count_priority("high"),
    "medium_priority": _count_priority("medium"),
    "low_priority": _count_priority("low"),
    "national_project_money": _count_type(NATIONAL_MONEY_TYPES),
    "ir_disclosure": _count_type(IR_TYPES),
  }


def get_strategic_watch_caution_text() -> str:
  return STRATEGIC_WATCH_CAUTION_JA


def load_strategic_watch_artifacts(
  project_root: Path | str,
  publication_number: str | None = None,
  brief_dir: str | Path | None = None,
) -> StrategicWatchUIArtifacts:
  root = Path(project_root)
  pub = publication_number or DEFAULT_BRIEF_PUB
  if brief_dir:
    bdir = Path(brief_dir)
    if not bdir.is_absolute():
      bdir = root / bdir
  else:
    bdir = _brief_dir_for_pub(root, pub)

  missing: list[str] = []
  errors: list[str] = []

  paths = {key: bdir / filename for key, filename in ARTIFACT_FILES.items()}
  for key, path in paths.items():
    if not path.exists():
      missing.append(key)

  items_df = safe_read_csv(paths["items_csv"])
  top_df = safe_read_csv(paths["top_items_csv"])
  brief_md = safe_read_text(paths["brief_md"])
  actions_md = safe_read_text(paths["next_actions_md"])

  status = _compute_loader_status(missing, items_df)
  return StrategicWatchUIArtifacts(
    publication_number=pub,
    status=status,
    brief_dir=str(bdir),
    watch_items_df=_normalize_df(items_df),
    top_watch_items_df=_normalize_df(top_df),
    brief_md=brief_md,
    next_actions_md=actions_md,
    missing_artifacts=missing,
    errors=errors,
  )


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
  if df.empty:
    return df
  out = df.copy()
  for col in out.columns:
    out[col] = out[col].apply(normalize_display_value)
  return out


def render_strategic_watch_caution_cards() -> None:
  st.markdown(render_caution_box(STRATEGIC_WATCH_CAUTION_JA), unsafe_allow_html=True)
  st.markdown(
    render_warning_box(
      f"{WATCH_PRIORITY_NOTE} "
      "high priority は注目度が高い候補であり、事実関係が確定した意味ではありません。"
    ),
    unsafe_allow_html=True,
  )


def render_strategic_watch_summary_cards(artifacts: StrategicWatchUIArtifacts) -> None:
  counts = get_strategic_watch_status_counts(artifacts)
  cards = [
    ("Watch Items", counts["watch_items"]),
    ("Top Watch Items", counts["top_watch_items"]),
    ("High Priority", counts["high_priority"]),
    ("Medium Priority", counts["medium_priority"]),
    ("Low Priority", counts["low_priority"]),
    ("National Project / Money", counts["national_project_money"]),
    ("IR / Disclosure", counts["ir_disclosure"]),
  ]
  st.markdown(render_metric_cards(cards), unsafe_allow_html=True)


def _render_watch_table(df: pd.DataFrame, columns: tuple[str, ...]) -> None:
  display_df = prepare_strategic_watch_display_df(df, columns)
  if display_df.empty:
    st.info("該当する Watch Item はまだありません。（0件）")
    return
  render_dataframe_stretch(display_df, hide_index=True)


def render_top_strategic_watch_items(artifacts: StrategicWatchUIArtifacts) -> None:
  st.subheader("Top Strategic Watch Items")
  st.markdown(
    render_info_box(
      "Top items are monitoring candidates with stronger thematic overlap. "
      "They are not confirmed facts."
    ),
    unsafe_allow_html=True,
  )
  source_df = artifacts.top_watch_items_df
  if source_df.empty and not artifacts.watch_items_df.empty:
    source_df = artifacts.watch_items_df.head(10)
  _render_watch_table(source_df, TOP_WATCH_COLUMNS)


def render_national_project_money_signals(artifacts: StrategicWatchUIArtifacts) -> None:
  st.subheader("National Project / Money Signals")
  df = artifacts.watch_items_df
  if df.empty or "watch_type" not in df.columns:
    st.info("National Project / Money Signals は0件です。")
    return
  filtered = df[df["watch_type"].astype(str).isin(NATIONAL_MONEY_TYPES)]
  _render_watch_table(
    filtered,
    (
      "watch_theme",
      "watch_priority",
      "related_web_signal_title",
      "related_web_signal_domain",
      "source_quality",
      "link_score",
      "why_it_matters",
      "related_web_signal_url",
    ),
  )


def render_ir_disclosure_signals(artifacts: StrategicWatchUIArtifacts) -> None:
  st.subheader("IR / Disclosure Signals")
  df = artifacts.watch_items_df
  if df.empty or "watch_type" not in df.columns:
    st.info("IR / Disclosure Signals は0件です。")
    return
  filtered = df[df["watch_type"].astype(str).isin(IR_TYPES)]
  if filtered.empty:
    st.info("IR / Disclosure Signals は0件です。次Phaseで EDINET / 企業IR を拡張予定です。")
    return
  _render_watch_table(
    filtered,
    (
      "watch_theme",
      "watch_priority",
      "related_web_signal_title",
      "related_web_signal_domain",
      "why_it_matters",
      "next_verification_action",
      "related_web_signal_url",
    ),
  )


def render_patent_paper_web_candidates(artifacts: StrategicWatchUIArtifacts) -> None:
  st.subheader("Patent × Paper × Web Signal Candidates")
  df = artifacts.watch_items_df
  if df.empty or "watch_type" not in df.columns:
    st.info("Patent × Paper × Web Signal Candidates は0件です。")
    return
  filtered = df[df["watch_type"].astype(str).isin(PATENT_PAPER_WEB_TYPES)]
  _render_watch_table(
    filtered,
    (
      "watch_theme",
      "watch_priority",
      "related_paper_title",
      "related_web_signal_title",
      "link_score",
      "link_confidence",
      "why_it_matters",
      "next_verification_action",
    ),
  )


def render_evidence_gaps_section(artifacts: StrategicWatchUIArtifacts) -> None:
  st.subheader("Evidence Gaps")
  gaps: list[str] = []
  if not artifacts.watch_items_df.empty and "evidence_gap" in artifacts.watch_items_df.columns:
    for value in artifacts.watch_items_df["evidence_gap"].astype(str).unique():
      if value and value != NOT_AVAILABLE:
        gaps.append(value[:300])
  if not gaps:
    gaps = [
      "Target patent description/examples are not yet verified.",
      "Web signal to patent direct linkage is not confirmed.",
      "Papers are supporting evidence candidates only.",
    ]
  gap_html = "".join(f"<li>{gap}</li>" for gap in gaps[:6])
  st.markdown(render_warning_box(f"<ul>{gap_html}</ul>"), unsafe_allow_html=True)


def render_next_verification_actions_section(artifacts: StrategicWatchUIArtifacts) -> None:
  st.subheader("Next Verification Actions")
  if artifacts.next_actions_md:
    with st.expander("Strategic Watch Next Actions (Markdown)"):
      st.markdown(render_markdown_preview(artifacts.next_actions_md))
  elif not artifacts.watch_items_df.empty and "next_verification_action" in artifacts.watch_items_df.columns:
    actions = artifacts.watch_items_df["next_verification_action"].astype(str).unique().tolist()
    for action in actions[:8]:
      if action and action != NOT_AVAILABLE:
        st.markdown(f"- {action}")
  else:
    st.info("Next Verification Actions は not available です。")


def render_strategic_watch_brief_markdown(artifacts: StrategicWatchUIArtifacts) -> None:
  st.subheader("Strategic Watch Brief Markdown")
  if artifacts.brief_md:
    with st.expander("strategic_watch_brief.md", expanded=False):
      st.markdown(render_markdown_preview(artifacts.brief_md, max_chars=8000))
  else:
    st.info("strategic_watch_brief.md は not available です。")


def render_strategic_watch_section(artifacts: StrategicWatchUIArtifacts) -> None:
  st.markdown("## Strategic Watch Brief")
  if artifacts.status == "missing":
    st.warning(MISSING_ARTIFACT_WARNING)
    render_strategic_watch_caution_cards()
    render_strategic_watch_summary_cards(artifacts)
    return

  if artifacts.missing_artifacts:
    st.warning(
      f"一部の成果物が見つかりません: {', '.join(artifacts.missing_artifacts)}。"
      " 表示可能な範囲で partial 表示します。"
    )

  render_strategic_watch_caution_cards()
  render_strategic_watch_summary_cards(artifacts)
  render_top_strategic_watch_items(artifacts)
  render_national_project_money_signals(artifacts)
  render_ir_disclosure_signals(artifacts)
  render_patent_paper_web_candidates(artifacts)
  render_evidence_gaps_section(artifacts)
  render_next_verification_actions_section(artifacts)
  render_strategic_watch_brief_markdown(artifacts)

  st.markdown(
    render_info_box(
      "This is not FTO, infringement, or validity analysis. "
      + BRIEF_CAUTION.splitlines()[0]
    ),
    unsafe_allow_html=True,
  )
