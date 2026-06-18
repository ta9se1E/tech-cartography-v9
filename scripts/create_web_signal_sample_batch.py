#!/usr/bin/env python3
"""Create a manual Web Signal sample batch without Tavily API (Phase 23.0)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.web_signals.schema import (
  WebSignal,
  WebSignalBatch,
  apply_validation_rules,
  new_batch_id,
  new_signal_id,
  utc_now_iso,
  validate_web_signal,
)
from tech_cartography.web_signals.store import SOURCE_POLICY_VERSION, save_web_signal_batch


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Create a Web Signal sample batch (no Tavily API)")
  parser.add_argument("--topic", required=True)
  parser.add_argument("--output-dir", required=True)
  parser.add_argument(
    "--include-synthetic-examples",
    action="store_true",
    default=False,
    help="Include clearly labeled synthetic demo signals only",
  )
  parser.add_argument("--empty", action="store_true", default=False, help="Create an empty batch")
  return parser.parse_args()


def _build_synthetic_examples(topic: str) -> list[WebSignal]:
  now = utc_now_iso()
  return [
    WebSignal(
      signal_id=new_signal_id(),
      signal_type="national_project",
      source_title="Example national project placeholder",
      source_url="https://example.invalid/synthetic/national-project",
      source_domain="example.invalid",
      collected_at=now,
      query=topic,
      raw_snippet="Synthetic demo signal placeholder for national project workflow.",
      related_project="Example Project (Synthetic)",
      related_technology_terms=["PAN", "carbon fiber"],
      confidence="low",
      verification_status="synthetic_demo",
      is_synthetic_demo=True,
      caveat="Synthetic demo signal. This is not real-world evidence.",
      next_verification_action="Replace with verified public funding source such as JST/NEDO pages.",
    ),
    WebSignal(
      signal_id=new_signal_id(),
      signal_type="human",
      source_title="Example researcher role placeholder",
      source_url="https://example.invalid/synthetic/human-signal",
      source_domain="example.invalid",
      collected_at=now,
      query=topic,
      raw_snippet="Synthetic demo signal placeholder for human signal candidate.",
      related_person="Example Person (Synthetic)",
      related_institution="Example Lab (Synthetic)",
      confidence="weak",
      verification_status="synthetic_demo",
      is_synthetic_demo=True,
      caveat="Synthetic demo signal. This is not real-world evidence.",
      next_verification_action="Verify against official university or company pages.",
    ),
  ]


def main() -> int:
  args = parse_args()
  output_dir = Path(args.output_dir)
  if not output_dir.is_absolute():
    output_dir = PROJECT_ROOT / output_dir

  signals: list[WebSignal] = []
  notes = "Empty sample batch. No Tavily API execution. No real-world web signals included."
  if args.empty:
    pass
  elif args.include_synthetic_examples:
    signals = [_apply(sig) for sig in _build_synthetic_examples(args.topic)]
    notes = (
      "Synthetic demo signals only. These are placeholders for schema/testing. "
      "Not real-world evidence."
    )
  else:
    notes = (
      "Batch scaffold only. Use --include-synthetic-examples for labeled synthetic demo signals."
    )

  batch = WebSignalBatch(
    batch_id=new_batch_id(),
    topic=args.topic,
    created_at=utc_now_iso(),
    query_set=[args.topic],
    signals=signals,
    source_policy_version=SOURCE_POLICY_VERSION,
    notes=notes,
  )

  for signal in batch.signals:
    errors = validate_web_signal(signal)
    if errors:
      raise ValueError(f"Invalid synthetic sample signal {signal.signal_id}: {errors}")

  paths = save_web_signal_batch(batch, output_dir)
  print(
    json.dumps(
      {
        "batch_id": batch.batch_id,
        "signal_count": len(batch.signals),
        "output_paths": {key: str(path) for key, path in paths.items()},
        "notes": batch.notes,
      },
      indent=2,
      ensure_ascii=False,
    ),
  )
  return 0


def _apply(signal: WebSignal) -> WebSignal:
  return apply_validation_rules(signal)


if __name__ == "__main__":
  raise SystemExit(main())
