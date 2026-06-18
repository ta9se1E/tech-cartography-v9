"""Persist Strategic Watch Brief outputs (Phase 23.5)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from tech_cartography.reports.project_export import save_records_csv
from tech_cartography.strategic_watch.brief_builder import (
  WATCH_ITEM_CSV_COLUMNS,
  render_strategic_watch_brief_md,
  render_strategic_watch_next_actions_md,
  strategic_watch_items_to_dataframe,
)
from tech_cartography.strategic_watch.schema import StrategicWatchBrief


def save_strategic_watch_brief(brief: StrategicWatchBrief, output_dir: Path | str) -> dict[str, Path]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)

  json_path = out / "strategic_watch_brief.json"
  items_csv_path = out / "strategic_watch_items.csv"
  top_csv_path = out / "top_strategic_watch_items.csv"
  brief_md_path = out / "strategic_watch_brief.md"
  actions_md_path = out / "strategic_watch_next_actions.md"

  json_path.write_text(json.dumps(brief.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

  all_df = strategic_watch_items_to_dataframe(brief.watch_items)
  top_df = strategic_watch_items_to_dataframe(brief.top_watch_items)
  save_records_csv(all_df.to_dict(orient="records"), items_csv_path)
  save_records_csv(top_df.to_dict(orient="records"), top_csv_path)

  brief_md_path.write_text(render_strategic_watch_brief_md(brief), encoding="utf-8")
  actions_md_path.write_text(render_strategic_watch_next_actions_md(brief), encoding="utf-8")

  return {
    "strategic_watch_brief_json": json_path,
    "strategic_watch_items_csv": items_csv_path,
    "top_strategic_watch_items_csv": top_csv_path,
    "strategic_watch_brief_md": brief_md_path,
    "strategic_watch_next_actions_md": actions_md_path,
  }


def load_strategic_watch_brief_json(path: Path | str) -> dict:
  p = Path(path)
  if not p.exists():
    return {}
  return json.loads(p.read_text(encoding="utf-8"))
