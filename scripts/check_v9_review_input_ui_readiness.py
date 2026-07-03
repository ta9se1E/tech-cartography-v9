"""Readiness checks for the v9 human review input UI."""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.review_state import default_review_state  # noqa: E402
from ui_v9.labels import review_priority_value_ja  # noqa: E402
from ui_v9.signal_watch_app import _prepare_display_signal_dicts, _stable_signal_id  # noqa: E402
from ui_v9.tabs import _get_review_for_signal  # noqa: E402


def main() -> int:
  errors: list[str] = []

  read_now = {"title": "A", "action": "Read Now"}
  watch = {"title": "B", "action": "Watch"}
  ignore = {"title": "C", "action": "Ignore"}

  if default_review_state(read_now)["review_decision"] != "採用":
    errors.append("Read Nowから採用初期値を作れません")
  if default_review_state(watch)["review_decision"] != "保留":
    errors.append("Watchから保留初期値を作れません")
  if default_review_state(ignore)["review_decision"] != "見送り":
    errors.append("Ignoreから見送り初期値を作れません")

  if review_priority_value_ja("高") != 1 or review_priority_value_ja("中") != 2 or review_priority_value_ja("低") != 3:
    errors.append("高/中/低を1/2/3へ変換できません")

  signal_without_id = {
    "title": "PAN precursor update",
    "type": "patent",
    "source_url": "https://example.com/signal",
    "source_name": "Demo Source",
    "published_date": "2026-07-04",
    "summary": "前駆体の比較",
    "tags": ["PAN"],
    "companies": ["Demo Corp"],
    "action": "Read Now",
  }
  stable_id = _stable_signal_id(signal_without_id, index=0)
  if not stable_id.startswith("generated_"):
    errors.append("stable signal IDを生成できません")

  reviews_by_signal_id = {
    stable_id: {
      "review_decision": "採用",
      "review_priority": 1,
      "review_comment": "今週確認する",
      "reviewed": True,
    }
  }
  resolved = _get_review_for_signal(signal_without_id, stable_id, reviews_by_signal_id)
  if resolved["review_comment"] != "今週確認する":
    errors.append("reviews_by_signal_id相当のdictへ保存したレビューを取得できません")

  multi_signals = [
    {**signal_without_id, "title": "A"},
    {**signal_without_id, "title": "B", "source_url": "https://example.com/b"},
  ]
  display = _prepare_display_signal_dicts(multi_signals, {"schema_version": "v9.2"}, reviews_by_signal_id)
  if len({item["id"] for item in display}) != 2:
    errors.append("複数Signalのreviewが混在しないID付与に失敗しました")

  original = deepcopy(signal_without_id)
  _prepare_display_signal_dicts([signal_without_id], {"schema_version": "v9.2"}, {})
  if signal_without_id != original:
    errors.append("元Signalを変更しています")

  if errors:
    print("[v9 review input ui readiness] NG:")
    for error in errors:
      print(f"- {error}")
    return 1

  print("[v9 review input ui readiness] OK: human review input UI is ready.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
