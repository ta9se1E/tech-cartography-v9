"""Local persistence helpers for Tech Cartography v9."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def get_v9_runs_dir() -> Path:
  return PROJECT_ROOT / "data" / "v9_runs"


def ensure_v9_run_dirs(base_dir: Path | None = None) -> dict[str, Path]:
  root = Path(base_dir) if base_dir is not None else get_v9_runs_dir()
  snapshots_dir = root / "snapshots"
  digests_dir = root / "digests"
  try:
    root.mkdir(parents=True, exist_ok=True)
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    digests_dir.mkdir(parents=True, exist_ok=True)
  except OSError as exc:
    raise RuntimeError(f"v9保存先ディレクトリを作成できませんでした: {exc}") from exc
  return {
    "root": root,
    "snapshots": snapshots_dir,
    "digests": digests_dir,
    "watch_profile": root / "watch_profile_current.json",
  }


def _json_dump(path: Path, payload: dict[str, Any]) -> None:
  try:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
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


def save_watch_profile(profile: dict[str, Any], base_dir: Path | None = None) -> Path:
  dirs = ensure_v9_run_dirs(base_dir)
  path = dirs["watch_profile"]
  _json_dump(path, profile)
  return path


def load_watch_profile(
  default_profile: dict[str, Any] | None = None,
  base_dir: Path | None = None,
) -> dict[str, Any]:
  dirs = ensure_v9_run_dirs(base_dir)
  path = dirs["watch_profile"]
  if not path.exists():
    return dict(default_profile or {})
  return _json_load(path)


def save_snapshot(
  signals: list[dict[str, Any]],
  watch_profile: dict[str, Any],
  run_note: str = "",
  base_dir: Path | None = None,
) -> Path:
  dirs = ensure_v9_run_dirs(base_dir)
  snapshot_id = _build_next_snapshot_id(base_dir)
  path = dirs["snapshots"] / f"{snapshot_id}_snapshot.json"
  payload = {
    "snapshot_id": snapshot_id,
    "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "run_note": run_note.strip(),
    "watch_profile": watch_profile,
    "signals": signals,
  }
  _json_dump(path, payload)
  return path


def list_snapshots(limit: int = 20, base_dir: Path | None = None) -> list[Path]:
  dirs = ensure_v9_run_dirs(base_dir)
  paths = sorted(dirs["snapshots"].glob("*_snapshot.json"), reverse=True)
  return paths[: max(limit, 0)]


def load_snapshot(path: Path) -> dict[str, Any]:
  return _json_load(path)


def save_digest_files(
  markdown: str,
  csv_text: str,
  json_text: str,
  snapshot_id: str,
  base_dir: Path | None = None,
) -> dict[str, Path]:
  dirs = ensure_v9_run_dirs(base_dir)
  digest_id = snapshot_id.strip() or _build_next_snapshot_id(base_dir)
  markdown_path = dirs["digests"] / f"{digest_id}_digest.md"
  csv_path = dirs["digests"] / f"{digest_id}_signals.csv"
  json_path = dirs["digests"] / f"{digest_id}_payload.json"
  try:
    markdown_path.write_text(markdown, encoding="utf-8")
    csv_path.write_text(csv_text, encoding="utf-8")
    json_path.write_text(json_text, encoding="utf-8")
  except OSError as exc:
    raise RuntimeError(f"ダイジェストファイルを保存できませんでした: {exc}") from exc
  return {
    "markdown": markdown_path,
    "csv": csv_path,
    "json": json_path,
  }
