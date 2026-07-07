"""Static analysis helpers for Study Demo Simple Mode UI checks."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]

TECHNICAL_ID_PATTERNS = (
  re.compile(r"theme_[0-9a-f]{8,}"),
  re.compile(r"wp_theme_[0-9a-f]{8,}"),
  re.compile(r"plan_wp_theme_[0-9a-f]{8,}"),
  re.compile(r"study_demo_search_\d{8}_"),
  re.compile(r"run_origin\s*[:=]"),
  re.compile(r"context_type\s*[:=]"),
  re.compile(r"lineage_status\s*[:=]"),
  re.compile(r"signature\s*[:=]"),
  re.compile(r"active retrieval sources"),
  re.compile(r"provider_success_rate"),
  re.compile(r"search_run_count"),
  re.compile(r"raw/capped/deduped"),
)

LEGACY_TOOL_MARKERS = (
  "手動アップロード・旧データ投入機能",
  "CSVアップロード",
  "JSONアップロード",
  "legacy manifest",
  "ui_csv_upload",
  "ui_json_upload",
  "架空デモ12件",
)

DUPLICATE_HEADER_MARKERS = (
  'st.title("Tech Cartography v9")',
  'st.subheader("Tech Cartography v9")',
  "render_study_demo_capability_legend()",
  "render_study_demo_mode_legend()",
  "render_study_demo_banner()",
)

SIMPLE_UI_FILES = (
  "ui_v9/study_demo_simple_theme_ui.py",
  "ui_v9/study_demo_simple_sources_ui.py",
  "ui_v9/study_demo_simple_signals_ui.py",
  "ui_v9/study_demo_simple_tabs_ui.py",
  "ui_v9/study_demo_compact_components.py",
  "ui_v9/study_demo_research_value_ui.py",
  "ui_v9/study_demo_simple_signal_cards.py",
)


def _read(path: str) -> str:
  return (ROOT / path).read_text(encoding="utf-8")


def count_pattern_hits(text: str, patterns: Sequence[re.Pattern[str]]) -> int:
  return sum(len(pattern.findall(text)) for pattern in patterns)


def _simple_visible_source_text(text: str) -> str:
  lines: list[str] = []
  skip = 0
  for line in text.splitlines():
    if "should_show_technical_ids()" in line or "should_show_legacy_tools()" in line:
      if "if " in line:
        skip += 1
        continue
    if skip > 0:
      if line and not line.startswith((" ", "\t")):
        skip = 0
      else:
        continue
    if ".get('theme_id'" in line or '.get("theme_id"' in line or "key=" in line:
      continue
    if not any(token in line for token in ("st.write", "st.markdown", "st.caption", "st.info", "st.metric", "labels =", "format_func")):
      continue
    lines.append(line)
  return "\n".join(lines)


def analyze_simple_source_layout(*, mode: str = "simple") -> dict[str, Any]:
  app_source = _read("ui_v9/signal_watch_app.py")
  tabs_source = _read("ui_v9/tabs.py")
  simple_sources = "\n".join(_read(path) for path in SIMPLE_UI_FILES)

  duplicate_header_count = 0
  if "render_compact_header(" in app_source and 'st.title("Tech Cartography v9")' in app_source:
    if "is_study_demo_simple_ui()" in app_source and "if not is_study_demo_simple_ui()" in app_source:
      duplicate_header_count = 0
    else:
      duplicate_header_count = app_source.count('st.title("Tech Cartography v9")')

  duplicate_context_count = 0
  if tabs_source.count("render_active_analysis_banner(") > 0 and "is_study_demo_simple_ui()" in tabs_source:
    duplicate_context_count = 0
  elif tabs_source.count("render_active_analysis_banner(") > 1:
    duplicate_context_count = tabs_source.count("render_active_analysis_banner(") - 1

  technical_id_visible_count = 0
  legacy_tool_visible_count = 0
  if mode == "simple":
    for path in SIMPLE_UI_FILES:
      text = _simple_visible_source_text(_read(path))
      technical_id_visible_count += count_pattern_hits(text, TECHNICAL_ID_PATTERNS)
    legacy_text = _simple_visible_source_text(_read("ui_v9/study_demo_simple_sources_ui.py"))
    for marker in LEGACY_TOOL_MARKERS:
      if marker in legacy_text:
        legacy_tool_visible_count += 1

  collapsed_section_count = simple_sources.count("expanded=False")

  return {
    "duplicate_header_count": duplicate_header_count,
    "duplicate_context_count": duplicate_context_count,
    "technical_id_visible_count": technical_id_visible_count,
    "legacy_tool_visible_count": legacy_tool_visible_count,
    "collapsed_section_count": collapsed_section_count,
    "simple_ui_files_present": all((ROOT / path).is_file() for path in SIMPLE_UI_FILES),
  }


def analyze_signal_visibility(
  *,
  signals: Sequence[Any],
) -> dict[str, Any]:
  from services_v9.signal_models import Signal
  from ui_v9.study_demo_simple_signals_ui import filter_signals_for_simple_display, split_top_and_remaining

  parsed: list[Signal] = []
  for item in signals:
    if isinstance(item, Signal):
      parsed.append(item)
    else:
      parsed.append(Signal.from_dict(dict(item)))
  visible, hidden_empty = filter_signals_for_simple_display(parsed)
  top_reads, remaining = split_top_and_remaining(parsed)
  if len(top_reads) < 3 and len(visible) >= 3:
    top_reads = visible[:3]
    top_keys = {f"{s.type}:{s.title}:{s.source_name}" for s in top_reads}
    remaining = [item for item in visible if f"{item.type}:{item.title}:{item.source_name}" not in top_keys]
  top_keys = {f"{s.type}:{s.title}:{s.source_name}" for s in top_reads}
  duplicate_signal_count = sum(
    1 for item in remaining if f"{item.type}:{item.title}:{item.source_name}" in top_keys
  )
  return {
    "top_signal_count": len(top_reads),
    "remaining_signal_count": len(remaining),
    "duplicate_signal_count": duplicate_signal_count,
    "hidden_empty_title_count": hidden_empty,
    "visible_signal_count": len(visible),
  }


def build_simple_ui_check_result(
  *,
  fixture: Mapping[str, Any],
  mode: str = "simple",
) -> dict[str, Any]:
  from services_v9.study_demo_active_loader import build_temporary_search_source_payload
  from services_v9.study_demo_run_metrics import validate_run_metric_consistency
  from services_v9.study_demo_saved_theme_editor import apply_editor_selection_metadata

  context = dict(fixture.get("active_context", {}) or {})
  artifacts = dict(fixture.get("artifacts", {}) or {})
  themes = dict(fixture.get("themes", {}) or {})
  new_theme = dict(themes.get("new_theme", {}) or {})
  theme_state = apply_editor_selection_metadata({}, new_theme)
  search_run_id = str(fixture.get("search_run_id", "") or "")

  def _fake_client() -> Any:
    prefix = f"search_runs/{search_run_id}/"

    class _Blob:
      def __init__(self, name: str, payload: Any):
        self.name = name
        self._payload = payload

      def download_as_bytes(self) -> bytes:
        import json

        return json.dumps(self._payload).encode()

    class _Bucket:
      def list_blobs(self, *, prefix: str = ""):
        for key, value in artifacts.items():
          yield _Blob(f"{prefix}{key}", value)

    class _Client:
      def bucket(self, _name: str) -> _Bucket:
        return _Bucket()

    return _Client()

  source = build_temporary_search_source_payload(context, storage_client=_fake_client())
  metrics = dict(source.get("canonical_metrics", {}) or {})
  inconsistencies = validate_run_metric_consistency(metrics)

  layout = analyze_simple_source_layout(mode=mode)
  integrated = dict(artifacts.get("integrated_signals.json", {}) or {})
  signal_rows = list(integrated.get("signals", []) or [])
  signal_stats = analyze_signal_visibility(signals=signal_rows)

  initial_visible_sections_by_tab = {
    "theme": ["current_theme_card", "search_conditions_collapsed"],
    "sources": ["provider_cards", "integrated_summary"],
    "signals": ["top3_cards", "remaining_collapsed"],
    "weekly": ["baseline_summary"],
    "watch_profile": ["profile_summary"],
    "digest": ["top3", "downloads"],
  }

  status = "ok"
  if layout["duplicate_header_count"] > 0:
    status = "blocked"
  if layout["duplicate_context_count"] > 0 and mode == "simple":
    status = "blocked"
  if mode == "simple" and layout["technical_id_visible_count"] > 0:
    status = "blocked"
  if mode == "simple" and layout["legacy_tool_visible_count"] > 0:
    status = "blocked"
  if signal_stats["duplicate_signal_count"] > 0:
    status = "blocked"
  if inconsistencies:
    status = "blocked"

  return {
    "status": status,
    "mode": mode,
    "selected_theme_id": theme_state.get("selected_saved_theme_id"),
    "active_run": context.get("active_search_run_id"),
    "lineage_status": context.get("lineage_status"),
    "provider_counts": metrics.get("provider_counts"),
    "integrated_count": metrics.get("integrated_count"),
    "tier_counts": metrics.get("tier_counts"),
    "metric_inconsistency_count": len(inconsistencies),
    "initial_visible_sections_by_tab": initial_visible_sections_by_tab,
    "external_api_calls": 0,
    "cloud_writes": 0,
    "production_modifications": False,
    **layout,
    **signal_stats,
  }


__all__ = [
  "analyze_signal_visibility",
  "analyze_simple_source_layout",
  "build_simple_ui_check_result",
]
