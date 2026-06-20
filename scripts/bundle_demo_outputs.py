#!/usr/bin/env python3
"""Copy US demo artifacts into demo_outputs/US-12565719-B2 for Cloud Run upload."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from tech_cartography.runtime.demo_output_paths import (  # noqa: E402
  BUNDLE_COPY_SOURCES,
  DEMO_PUBLICATION_NUMBER,
  REQUIRED_BUNDLE_FILES,
  demo_bundle_dir,
)


def main() -> int:
  target_dir = demo_bundle_dir(PROJECT_ROOT)
  target_dir.mkdir(parents=True, exist_ok=True)
  copied = 0
  skipped = 0
  for source_rel, bundle_name in BUNDLE_COPY_SOURCES:
    source = PROJECT_ROOT / source_rel
    dest = target_dir / bundle_name
    if not source.exists():
      print(f"SKIP missing source: {source_rel}")
      skipped += 1
      continue
    shutil.copy2(source, dest)
    copied += 1
    print(f"COPY {source_rel} -> demo_outputs/{DEMO_PUBLICATION_NUMBER}/{bundle_name}")

  missing_required = [
    name
    for name in REQUIRED_BUNDLE_FILES
    if not (target_dir / name).exists()
  ]
  print(f"Copied: {copied}, skipped sources: {skipped}")
  if missing_required:
    print("Missing required bundle files:")
    for name in missing_required:
      print(f"  - {name}")
    return 1
  print(f"Bundle ready: {target_dir}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
