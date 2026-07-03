"""Readiness checks for the bilingual v9.2 watch profile input."""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.demo_data import load_demo_signals_payload, load_demo_watch_profile_payload  # noqa: E402
from services_v9.digest_export import build_weekly_digest_markdown  # noqa: E402
from services_v9.persistence import load_snapshot, save_snapshot  # noqa: E402
from services_v9.query_preview import build_query_preview_bundle  # noqa: E402
from services_v9.signal_models import Signal, WatchProfile  # noqa: E402
from services_v9.signal_scoring import enrich_signals  # noqa: E402
from services_v9.watch_profile_schema import (  # noqa: E402
  default_bilingual_watch_profile,
  migrate_watch_profile,
  parse_publication_numbers,
  parse_terms,
  split_terms,
)


def main() -> int:
  errors: list[str] = []

  default_profile = default_bilingual_watch_profile()
  if default_profile.get("schema_version") != "v9.2":
    errors.append("default bilingual watch profile が v9.2 ではありません")

  demo_profile = migrate_watch_profile(load_demo_watch_profile_payload())
  if demo_profile.get("schema_version") != "v9.2":
    errors.append("demo watch profile を v9.2 として読み込めません")

  old_profile = {
    "theme": "旧形式テーマ",
    "include_keywords": ["PAN carbon fiber precursor", "表面欠陥", "表面欠陥"],
    "exclude_keywords": ["graphene"],
    "target_companies": ["東レ"],
    "source_types": ["patent", "paper"],
    "countries": ["JP"],
    "cadence": "Weekly",
    "priority_rules": ["旧形式ルール"],
  }
  migrated_old = migrate_watch_profile(old_profile)
  if migrated_old.get("theme_name") != "旧形式テーマ":
    errors.append("旧Watch Profileのmigrationに失敗しました")

  if split_terms("a,b\nc、d；e;f") != ["a", "b", "c", "d", "e", "f"]:
    errors.append("split_terms が複数区切りを扱えません")
  if parse_terms("surface defect, internal void\nsurface defect") != ["surface defect", "internal void"]:
    errors.append("英語キーワードのparse/重複除去に失敗しました")
  if parse_terms("表面欠陥、内部ボイド\n表面欠陥") != ["表面欠陥", "内部ボイド"]:
    errors.append("日本語キーワードのparse/重複除去に失敗しました")
  parsed_publications = parse_publication_numbers("JP-2022-090764-A\njp2023163084a\nJP2022090764A")
  if parsed_publications != ["JP2022090764A", "JP2023163084A"]:
    errors.append("publication number の正規化に失敗しました")

  previews = build_query_preview_bundle(demo_profile)
  if set(previews) != {"patent", "paper", "web", "company"}:
    errors.append("query preview bundle が4種類を返しません")

  signals = enrich_signals([Signal.from_dict(item) for item in load_demo_signals_payload()])
  digest = build_weekly_digest_markdown(signals, WatchProfile.from_dict(demo_profile))
  if "## 監視テーマ" not in digest:
    errors.append("digest markdown に監視テーマ情報が含まれません")
  if "Seed公報" not in digest:
    errors.append("digest markdown に Seed公報情報が含まれません")

  with TemporaryDirectory() as tmp_dir:
    snapshot_path = save_snapshot(
      [signal.to_dict() for signal in signals],
      demo_profile,
      run_note="bilingual readiness",
      base_dir=Path(tmp_dir) / "v9_runs",
    )
    loaded_snapshot = load_snapshot(snapshot_path)
    if loaded_snapshot.get("watch_profile", {}).get("schema_version") != "v9.2":
      errors.append("snapshot に新Watch Profileが含まれていません")

  if errors:
    print("[v9 bilingual profile readiness] NG:")
    for error in errors:
      print(f"- {error}")
    return 1

  print("[v9 bilingual profile readiness] OK: bilingual watch profile input is ready.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
