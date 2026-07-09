"""Local persistence helpers for Tech Cartography v9."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .cloud_runtime import get_persist_root
from .watch_profile_schema import default_bilingual_watch_profile, migrate_watch_profile

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def get_v9_runs_dir() -> Path:
  return get_persist_root()


def ensure_v9_run_dirs(base_dir: Path | None = None) -> dict[str, Path]:
  root = Path(base_dir) if base_dir is not None else get_v9_runs_dir()
  snapshots_dir = root / "snapshots"
  digests_dir = root / "digests"
  config_dir = root / "v9_config"
  try:
    root.mkdir(parents=True, exist_ok=True)
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    digests_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
  except OSError as exc:
    raise RuntimeError(f"v9保存先ディレクトリを作成できませんでした: {exc}") from exc
  return {
    "root": root,
    "snapshots": snapshots_dir,
    "digests": digests_dir,
    "config": config_dir,
    "watch_profile": root / "watch_profile_current.json",
  }


def _json_dump(path: Path, payload: dict[str, Any]) -> None:
  try:
    write_json_atomic(path, payload)
  except OSError as exc:
    raise RuntimeError(f"ファイルを保存できませんでした: {path} ({exc})") from exc


def _json_load(path: Path) -> dict[str, Any]:
  try:
    return json.loads(path.read_text(encoding="utf-8"))
  except FileNotFoundError as exc:
    raise RuntimeError(f"ファイルが見つかりません: {path}") from exc
  except json.JSONDecodeError as exc:
    raise RuntimeError(f"JSONの読み込みに失敗しました: {path} ({exc})") from exc
  except OSError as exc:
    raise RuntimeError(f"ファイルを読み込めませんでした: {path} ({exc})") from exc


def _build_next_snapshot_id(base_dir: Path | None = None) -> str:
  dirs = ensure_v9_run_dirs(base_dir)
  prefix = datetime.now().astimezone().strftime("%Y-%m-%d")
  existing = []
  for path in dirs["snapshots"].glob(f"{prefix}_*_snapshot.json"):
    stem = path.name.removesuffix("_snapshot.json")
    parts = stem.split("_")
    if len(parts) >= 2 and parts[-1].isdigit():
      existing.append(int(parts[-1]))
  next_index = max(existing, default=0) + 1
  return f"{prefix}_{next_index:03d}"


def _assert_study_demo_persist_write_allowed(operation: str) -> None:
  from .study_demo_config import is_study_demo_mode
  from .study_demo_guard import assert_write_allowed

  if is_study_demo_mode():
    assert_write_allowed(operation)


def save_watch_profile(profile: dict[str, Any], base_dir: Path | None = None) -> Path:
  _assert_study_demo_persist_write_allowed("watch_profile")
  dirs = ensure_v9_run_dirs(base_dir)
  path = dirs["watch_profile"]
  _json_dump(path, migrate_watch_profile(profile))
  return path


def load_watch_profile(
  default_profile: dict[str, Any] | None = None,
  base_dir: Path | None = None,
) -> dict[str, Any]:
  dirs = ensure_v9_run_dirs(base_dir)
  path = dirs["watch_profile"]
  if not path.exists():
    return migrate_watch_profile(default_profile or default_bilingual_watch_profile())
  return migrate_watch_profile(_json_load(path))


def save_snapshot(
  signals: list[dict[str, Any]],
  watch_profile: dict[str, Any],
  run_note: str = "",
  base_dir: Path | None = None,
) -> Path:
  _assert_study_demo_persist_write_allowed("snapshot")
  dirs = ensure_v9_run_dirs(base_dir)
  snapshot_id = _build_next_snapshot_id(base_dir)
  path = dirs["snapshots"] / f"{snapshot_id}_snapshot.json"
  payload = {
    "snapshot_id": snapshot_id,
    "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "run_note": run_note.strip(),
    "watch_profile": migrate_watch_profile(watch_profile),
    "signals": signals,
  }
  _json_dump(path, payload)
  return path


def list_snapshots(limit: int = 20, base_dir: Path | None = None) -> list[Path]:
  dirs = ensure_v9_run_dirs(base_dir)
  paths = sorted(dirs["snapshots"].glob("*_snapshot.json"), reverse=True)
  return paths[: max(limit, 0)]


def load_snapshot(path: Path) -> dict[str, Any]:
  payload = _json_load(path)
  payload["watch_profile"] = migrate_watch_profile(payload.get("watch_profile", {}))
  return payload


def save_digest_files(
  markdown: str,
  csv_text: str,
  json_text: str,
  snapshot_id: str,
  base_dir: Path | None = None,
) -> dict[str, Path]:
  _assert_study_demo_persist_write_allowed("digest")
  dirs = ensure_v9_run_dirs(base_dir)
  digest_id = snapshot_id.strip() or _build_next_snapshot_id(base_dir)
  markdown_path = dirs["digests"] / f"{digest_id}_digest.md"
  csv_path = dirs["digests"] / f"{digest_id}_signals.csv"
  json_path = dirs["digests"] / f"{digest_id}_payload.json"
  try:
    write_text_atomic(markdown_path, markdown)
    write_text_atomic(csv_path, csv_text)
    write_text_atomic(json_path, json_text)
  except OSError as exc:
    raise RuntimeError(f"ダイジェストファイルを保存できませんでした: {exc}") from exc
  return {
    "markdown": markdown_path,
    "csv": csv_path,
    "json": json_path,
  }


def write_text_atomic(path: Path, text: str, *, encoding: str = "utf-8") -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
  temp_path.write_text(text, encoding=encoding)
  temp_path.replace(path)


def write_json_atomic(path: Path, payload: Any) -> None:
  text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
  write_text_atomic(path, text)
