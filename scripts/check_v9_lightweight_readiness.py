"""Readiness checks for the Tech Cartography v9 lightweight signal watch app."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.demo_data import (  # noqa: E402
  DEMO_SIGNALS_PATH,
  DEMO_WATCH_PROFILE_PATH,
  load_demo_signals,
  load_demo_signals_payload,
  load_demo_watch_profile,
)
from services_v9.digest_export import build_weekly_digest_markdown  # noqa: E402
from services_v9.signal_models import VALID_ACTIONS, VALID_STATUSES  # noqa: E402
from services_v9.signal_scoring import enrich_signals  # noqa: E402
from ui_v9.labels import FORBIDDEN_UI_LABELS, V9_TAB_LABELS  # noqa: E402

REQUIRED_SIGNAL_FIELDS = {
  "id",
  "title",
  "type",
  "source_url",
  "source_name",
  "published_date",
  "score",
  "previous_score",
  "status",
  "action",
  "why_read",
  "what_to_check",
  "next_action",
  "tags",
  "companies",
}


def main() -> int:
  errors: list[str] = []

  if not DEMO_SIGNALS_PATH.exists():
    errors.append(f"missing demo signals json: {DEMO_SIGNALS_PATH}")
  if not DEMO_WATCH_PROFILE_PATH.exists():
    errors.append(f"missing demo watch profile json: {DEMO_WATCH_PROFILE_PATH}")

  payload = load_demo_signals_payload()
  if len(payload) < 10:
    errors.append(f"expected at least 10 demo signals, found {len(payload)}")

  for index, item in enumerate(payload):
    missing = sorted(REQUIRED_SIGNAL_FIELDS - set(item))
    if missing:
      errors.append(f"signal[{index}] missing fields: {', '.join(missing)}")
    status = item.get("status")
    action = item.get("action")
    if status not in VALID_STATUSES:
      errors.append(f"signal[{index}] has invalid status: {status}")
    if action not in VALID_ACTIONS:
      errors.append(f"signal[{index}] has invalid action: {action}")

  signals = enrich_signals(load_demo_signals())
  watch_profile = load_demo_watch_profile()
  digest = build_weekly_digest_markdown(signals, watch_profile)
  if "# Tech Cartography v9 週次ダイジェスト" not in digest:
    errors.append("digest markdown header was not generated")
  if "## 今週まず読むべき3件" not in digest:
    errors.append("digest markdown top3 section was not generated")
  if V9_TAB_LABELS != [
    "テーマ設定",
    "情報源",
    "注目シグナル",
    "週次更新",
    "監視プロファイル",
    "ダイジェスト / エクスポート",
  ]:
    errors.append("v9 tab labels are not fully Japanese")

  forbidden_in_tabs = [label for label in FORBIDDEN_UI_LABELS if label in V9_TAB_LABELS]
  if forbidden_in_tabs:
    errors.append(f"forbidden labels found in v9 tabs: {', '.join(forbidden_in_tabs)}")

  if errors:
    print("[v9 readiness] NG:")
    for error in errors:
      print(f"- {error}")
    return 1

  print("[v9 readiness] OK: lightweight signal watch app is ready.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
