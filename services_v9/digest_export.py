"""Digest and export helpers for the lightweight v9 signal watch app."""

from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Sequence

from .signal_models import Signal, WatchProfile
from .signal_scoring import (
  format_score_delta,
  select_diverse_top_signals,
  select_top_reads,
  suggest_watch_profile_updates,
  summarize_status_buckets,
)

LIGHTWEIGHT_NOTE = (
  "This is a lightweight signal watch preview. It does not provide legal judgment, "
  "FTO judgment, infringement judgment, patentability judgment, or technical validation."
)


def build_weekly_digest_markdown(signals: Sequence[Signal], watch_profile: WatchProfile) -> str:
  ranked = select_diverse_top_signals(signals, top_n=10)
  top_reads = select_top_reads(ranked, limit=3)
  buckets = summarize_status_buckets(ranked)
  suggestions = suggest_watch_profile_updates(ranked, watch_profile)
  first_by_type: dict[str, Signal] = {}
  for signal in ranked:
    first_by_type.setdefault(signal.type, signal)

  lines = [
    "# Tech Cartography v9 Weekly Digest",
    "",
    f"Theme: {watch_profile.theme}",
    "",
    "## This Week's Top 3 Reads",
  ]
  for index, signal in enumerate(top_reads, start=1):
    lines.extend(
      [
        f"{index}. **{signal.title}** ({signal.type}, score {signal.score:.2f}, {signal.status})",
        f"   - Why read: {signal.why_read}",
        f"   - What to check: {signal.what_to_check}",
        f"   - Next action: {signal.next_action}",
        f"   - Source: {signal.source_url}",
      ]
    )
  if not top_reads:
    lines.append("No signals are available yet.")

  lines.extend(["", "## What Changed Since Last Digest"])
  for status in ("New", "Rising", "Dropped"):
    items = buckets.get(status, [])
    if items:
      lines.append(f"- {status}: {len(items)} items. Lead signal: {items[0].title} ({format_score_delta(items[0])})")
    else:
      lines.append(f"- {status}: 0 items.")

  lines.extend(["", "## Patent / Paper / Web / Company Set"])
  for signal_type in ("patent", "paper", "web", "company"):
    signal = first_by_type.get(signal_type)
    if signal is None:
      lines.append(f"- {signal_type.title()}: no signal in current Top 10.")
      continue
    lines.append(
      f"- {signal_type.title()}: {signal.title} | why read: {signal.why_read} | next: {signal.next_action}"
    )

  lines.extend(["", "## Suggested Watch Profile Updates"])
  for suggestion in suggestions:
    lines.append(f"- {suggestion}")

  lines.extend(["", "## Next Actions"])
  next_actions = []
  for signal in top_reads:
    if signal.next_action not in next_actions:
      next_actions.append(signal.next_action)
  for action in next_actions[:3]:
    lines.append(f"- {action}")
  if not next_actions:
    lines.append("- Review new signals once demo data is refreshed.")

  lines.extend(
    [
      "",
      "## Notes",
      LIGHTWEIGHT_NOTE,
      "Demo data only. External APIs, PDF/OCR deep dive, and scheduler delivery are disabled in v9-0.",
    ]
  )
  return "\n".join(lines)


def signals_to_csv(signals: Sequence[Signal]) -> str:
  output = StringIO()
  writer = csv.DictWriter(
    output,
    fieldnames=[
      "id",
      "title",
      "type",
      "source_name",
      "source_url",
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
    ],
  )
  writer.writeheader()
  for signal in signals:
    writer.writerow(
      {
        "id": signal.id,
        "title": signal.title,
        "type": signal.type,
        "source_name": signal.source_name,
        "source_url": signal.source_url,
        "published_date": signal.published_date,
        "score": f"{signal.score:.2f}",
        "previous_score": "" if signal.previous_score is None else f"{signal.previous_score:.2f}",
        "status": signal.status,
        "action": signal.action,
        "why_read": signal.why_read,
        "what_to_check": signal.what_to_check,
        "next_action": signal.next_action,
        "tags": " | ".join(signal.tags),
        "companies": " | ".join(signal.companies),
      }
    )
  return output.getvalue()


def signals_to_json(signals: Sequence[Signal], watch_profile: WatchProfile) -> str:
  payload = {
    "app": "Tech Cartography v9",
    "mode": "lightweight_demo",
    "watch_profile": watch_profile.to_dict(),
    "signals": [signal.to_dict() for signal in signals],
    "notes": LIGHTWEIGHT_NOTE,
  }
  return json.dumps(payload, ensure_ascii=False, indent=2)
