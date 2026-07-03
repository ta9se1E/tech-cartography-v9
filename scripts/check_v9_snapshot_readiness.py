"""Readiness checks for Japanese snapshot persistence in Tech Cartography v9."""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.demo_data import load_demo_signals_payload, load_demo_watch_profile_payload  # noqa: E402
from services_v9.digest_export import build_weekly_digest_markdown, signals_to_csv, signals_to_json  # noqa: E402
from services_v9.persistence import (  # noqa: E402
  ensure_v9_run_dirs,
  list_snapshots,
  load_snapshot,
  load_watch_profile,
  save_digest_files,
  save_snapshot,
  save_watch_profile,
)
from services_v9.signal_models import Signal, WatchProfile  # noqa: E402
from services_v9.signal_scoring import enrich_signals  # noqa: E402
from services_v9.snapshot_diff import apply_snapshot_status, compare_snapshots  # noqa: E402
from ui_v9.labels import action_label_ja, status_label_ja, type_label_ja  # noqa: E402


def main() -> int:
  errors: list[str] = []

  gitkeep = PROJECT_ROOT / "data" / "v9_runs" / ".gitkeep"
  if not gitkeep.exists():
    errors.append("data/v9_runs/.gitkeep が存在しません")

  if type_label_ja("patent") != "特許":
    errors.append("type_label_ja が正しく変換できません")
  if status_label_ja("New") != "新規":
    errors.append("status_label_ja が正しく変換できません")
  if action_label_ja("Read Now") != "今すぐ読む":
    errors.append("action_label_ja が正しく変換できません")

  signals_payload = load_demo_signals_payload()
  watch_profile_payload = load_demo_watch_profile_payload()
  signals = enrich_signals([Signal.from_dict(item) for item in signals_payload])
  watch_profile = WatchProfile.from_dict(watch_profile_payload)
  digest_markdown = build_weekly_digest_markdown(signals, watch_profile)
  csv_text = signals_to_csv(signals)
  json_text = signals_to_json(signals, watch_profile)

  if "## 今週まず読むべき3件" not in digest_markdown:
    errors.append("日本語ダイジェスト見出しが生成されません")

  with TemporaryDirectory() as tmp_dir:
    base_dir = Path(tmp_dir) / "v9_runs"
    ensure_v9_run_dirs(base_dir)

    saved_profile_path = save_watch_profile(watch_profile_payload, base_dir=base_dir)
    loaded_profile = load_watch_profile(base_dir=base_dir)
    if loaded_profile.get("theme") != watch_profile_payload.get("theme"):
      errors.append("監視プロファイルの保存/読み込みに失敗しました")

    snapshot_path = save_snapshot(
      signals=[signal.to_dict() for signal in signals],
      watch_profile=watch_profile_payload,
      run_note="readiness",
      base_dir=base_dir,
    )
    snapshot_paths = list_snapshots(base_dir=base_dir)
    if not snapshot_paths:
      errors.append("snapshot一覧を取得できません")
    loaded_snapshot = load_snapshot(snapshot_path)
    if not loaded_snapshot.get("signals"):
      errors.append("snapshot読み込みに失敗しました")

    current_signals = [signal.to_dict() for signal in signals]
    current_signals[0]["score"] = float(current_signals[0]["score"]) + 0.15
    current_signals.append(
      {
        **current_signals[-1],
        "id": "demo-new-signal",
        "title": "新規追加のデモシグナル",
        "score": 0.81,
        "previous_score": None,
      }
    )
    current_signals = current_signals[:-1] + [current_signals[-1]]
    compared = apply_snapshot_status(current_signals, loaded_snapshot["signals"])
    diff = compare_snapshots(loaded_snapshot["signals"], compared)
    if diff["counts"]["New"] < 1:
      errors.append("snapshot比較で New を検出できません")
    if diff["counts"]["Rising"] < 1:
      errors.append("snapshot比較で Rising を検出できません")

    digest_paths = save_digest_files(
      digest_markdown,
      csv_text,
      json_text,
      snapshot_id=loaded_snapshot["snapshot_id"],
      base_dir=base_dir,
    )
    if not saved_profile_path.exists() or not all(path.exists() for path in digest_paths.values()):
      errors.append("ダイジェストファイル保存に失敗しました")

  if errors:
    print("[v9 snapshot readiness] NG:")
    for error in errors:
      print(f"- {error}")
    return 1

  print("[v9 snapshot readiness] OK: Japanese lightweight snapshot persistence is ready.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
