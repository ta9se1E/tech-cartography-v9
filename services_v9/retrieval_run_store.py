"""Persistent retrieval run manifest helpers for v9."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any

from .persistence import PROJECT_ROOT, ensure_v9_run_dirs, get_v9_runs_dir

RETRIEVAL_MANIFEST_SCHEMA_VERSION = "v9.5e"
RETRIEVAL_MANIFEST_DIRNAME = "retrieval_manifests"
SOURCE_TYPES = ("patent", "paper", "web_company")
_ARTIFACT_SUBDIRS = {
  "patent": "patent_retrieval_runs",
  "paper": "paper_retrieval_runs",
  "web_company": "web_company_retrieval_runs",
}
_STAGED_JSON_FILENAMES = {
  "patent": "patent_candidates_staged.json",
  "paper": "paper_candidates_staged.json",
  "web_company": "web_company_candidates_staged.json",
}


def stable_payload_signature(payload: object) -> str:
  serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
  return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_theme_id(watch_profile: dict[str, Any]) -> str:
  theme_payload = {
    "theme_name": str(watch_profile.get("theme_name", "") or "").strip(),
    "theme_description": str(watch_profile.get("theme_description", "") or "").strip(),
  }
  return stable_payload_signature(theme_payload)[:16]


def discover_retrieval_runs(
  base_dir: Path | str | None,
  source_type: str,
) -> list[dict[str, Any]]:
  normalized_source = _normalize_source_type(source_type)
  runs_dir = _artifact_runs_dir(base_dir, normalized_source)
  if not runs_dir.exists():
    return []
  loader = _loader_for_source(normalized_source)
  discovered: list[dict[str, Any]] = []
  for path in sorted(runs_dir.iterdir(), reverse=True):
    if not path.is_dir():
      continue
    payload = loader(_repo_relative_path(path))
    payload["artifact_dir"] = _repo_relative_path(path)
    discovered.append(payload)
  return discovered


def load_patent_retrieval_artifact(
  artifact_dir: Path | str,
) -> dict[str, Any]:
  return _load_retrieval_artifact("patent", artifact_dir)


def load_paper_retrieval_artifact(
  artifact_dir: Path | str,
) -> dict[str, Any]:
  return _load_retrieval_artifact("paper", artifact_dir)


def load_web_company_retrieval_artifact(
  artifact_dir: Path | str,
) -> dict[str, Any]:
  return _load_retrieval_artifact("web_company", artifact_dir)


def build_retrieval_run_manifest(
  watch_profile: dict[str, Any],
  source_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
  watch_profile_signature = stable_payload_signature(watch_profile)
  theme_name = str(watch_profile.get("theme_name", "") or "").strip()
  theme_id = build_theme_id(watch_profile)

  accepted_source_runs: dict[str, dict[str, Any]] = {}
  total_candidate_count = 0
  manifest_status = "success"
  for source_type in SOURCE_TYPES:
    raw = dict(source_runs.get(source_type, {}) or {})
    if not raw:
      continue
    status = _normalize_manifest_status(raw.get("status") or raw.get("provider_status"))
    candidate_count = int(raw.get("candidate_count", raw.get("rows_retrieved", 0)) or 0)
    if status == "failed" or candidate_count <= 0:
      continue
    if status == "partial_success":
      manifest_status = "partial_success"
    artifact_dir = _relative_artifact_dir(raw.get("artifact_dir") or raw.get("run_dir"))
    accepted_source_runs[source_type] = {
      "run_id": str(raw.get("run_id", raw.get("retrieval_run_id", "")) or "").strip(),
      "artifact_dir": artifact_dir,
      "status": status,
      "candidate_count": candidate_count,
    }
    total_candidate_count += candidate_count

  if not accepted_source_runs or total_candidate_count <= 0:
    raise ValueError("manifest に保存できる取得済み候補がありません。")

  manifest_seed = {
    "schema_version": RETRIEVAL_MANIFEST_SCHEMA_VERSION,
    "theme_id": theme_id,
    "theme_name": theme_name,
    "watch_profile_signature": watch_profile_signature,
    "source_runs": accepted_source_runs,
    "status": manifest_status,
    "data_origin": "retrieval_artifact",
  }
  manifest_id = stable_payload_signature(manifest_seed)[:24]
  return {
    "schema_version": RETRIEVAL_MANIFEST_SCHEMA_VERSION,
    "manifest_id": manifest_id,
    "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "theme_id": theme_id,
    "theme_name": theme_name,
    "watch_profile_signature": watch_profile_signature,
    "status": manifest_status,
    "source_runs": accepted_source_runs,
    "total_candidate_count": total_candidate_count,
    "data_origin": "retrieval_artifact",
  }


def save_retrieval_run_manifest(
  manifest: dict[str, Any],
  base_dir: Path | str | None = None,
) -> Path:
  manifest_id = str(manifest.get("manifest_id", "") or "").strip()
  if not manifest_id:
    raise ValueError("manifest_id がありません。")
  manifests_dir = _retrieval_manifests_dir(base_dir)
  target_dir = manifests_dir / manifest_id
  target_dir.mkdir(parents=True, exist_ok=True)
  path = target_dir / "retrieval_run_manifest.json"
  path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  return path


def load_retrieval_run_manifest(
  manifest_path: Path | str,
  *,
  base_dir: Path | str | None = None,
) -> dict[str, Any]:
  path = _resolve_manifest_path(manifest_path, base_dir=base_dir)
  payload = _load_json(path)
  payload["schema_version"] = str(payload.get("schema_version", "") or "")
  payload["manifest_id"] = str(payload.get("manifest_id", "") or "")
  payload["theme_id"] = str(payload.get("theme_id", "") or "")
  payload["theme_name"] = str(payload.get("theme_name", "") or "")
  payload["watch_profile_signature"] = str(payload.get("watch_profile_signature", "") or "")
  payload["status"] = _normalize_manifest_status(payload.get("status"))
  payload["total_candidate_count"] = int(payload.get("total_candidate_count", 0) or 0)
  payload["source_runs"] = {
    source_type: {
      "run_id": str(dict(item or {}).get("run_id", "") or "").strip(),
      "artifact_dir": str(dict(item or {}).get("artifact_dir", "") or "").strip(),
      "status": _normalize_manifest_status(dict(item or {}).get("status")),
      "candidate_count": int(dict(item or {}).get("candidate_count", 0) or 0),
    }
    for source_type, item in dict(payload.get("source_runs", {}) or {}).items()
    if source_type in SOURCE_TYPES and isinstance(item, dict)
  }
  return payload


def find_latest_compatible_manifest(
  base_dir: Path | str | None,
  watch_profile_signature: str,
) -> dict[str, Any] | None:
  manifests_dir = _retrieval_manifests_dir(base_dir)
  if not manifests_dir.exists():
    return None
  candidates: list[dict[str, Any]] = []
  for path in manifests_dir.glob("*/retrieval_run_manifest.json"):
    try:
      manifest = load_retrieval_run_manifest(path, base_dir=base_dir)
    except Exception:  # noqa: BLE001
      continue
    if str(manifest.get("watch_profile_signature", "") or "") != str(watch_profile_signature or ""):
      continue
    if str(manifest.get("status", "") or "") not in {"success", "partial_success"}:
      continue
    if int(manifest.get("total_candidate_count", 0) or 0) <= 0:
      continue
    candidates.append(manifest)
  if not candidates:
    return None
  candidates.sort(key=lambda item: str(item.get("created_at", "") or ""), reverse=True)
  return candidates[0]


def load_candidates_from_manifest(
  manifest: dict[str, Any],
) -> dict[str, Any]:
  loaded_candidates = {source_type: [] for source_type in SOURCE_TYPES}
  source_runs_out: dict[str, dict[str, Any]] = {}
  warnings: list[str] = []
  statuses: list[str] = []

  for source_type, run_info in dict(manifest.get("source_runs", {}) or {}).items():
    if source_type not in SOURCE_TYPES:
      continue
    loader = _loader_for_source(source_type)
    artifact_dir = str(dict(run_info or {}).get("artifact_dir", "") or "").strip()
    if not artifact_dir:
      warnings.append(f"{source_type}: artifact_dir がありません。")
      statuses.append("failed")
      continue
    try:
      loaded = loader(artifact_dir)
    except Exception as exc:  # noqa: BLE001
      warnings.append(f"{source_type}: artifact読込に失敗しました ({exc})")
      statuses.append("failed")
      continue
    loaded_candidates[source_type] = deepcopy(list(loaded.get("rows", []) or []))
    source_runs_out[source_type] = {
      "run_id": str(loaded.get("run_id", "") or ""),
      "artifact_dir": str(loaded.get("artifact_dir", artifact_dir) or artifact_dir),
      "status": str(loaded.get("status", "failed") or "failed"),
      "candidate_count": int(loaded.get("candidate_count", 0) or 0),
    }
    statuses.append(str(loaded.get("status", "failed") or "failed"))
    warnings.extend(list(loaded.get("warnings", []) or []))

  total_candidate_count = sum(len(rows) for rows in loaded_candidates.values())
  status = "failed"
  if total_candidate_count > 0:
    expected_source_count = len(dict(manifest.get("source_runs", {}) or {}))
    status = "success" if expected_source_count == len(statuses) and statuses and all(item == "success" for item in statuses) else "partial_success"
  return {
    "candidates_by_source": loaded_candidates,
    "source_runs": source_runs_out,
    "warnings": warnings,
    "status": status,
    "total_candidate_count": total_candidate_count,
  }


def _load_retrieval_artifact(source_type: str, artifact_dir: Path | str) -> dict[str, Any]:
  normalized_source = _normalize_source_type(source_type)
  target_dir = _resolve_artifact_dir(artifact_dir, normalized_source)
  staged_json_path = target_dir / _STAGED_JSON_FILENAMES[normalized_source]
  warnings: list[str] = []
  payload = _load_json(staged_json_path)
  rows = deepcopy(list(payload.get("rows", []) or []))
  raw_status = str(payload.get("provider_status", "") or "").strip()
  status = _normalize_manifest_status(raw_status)
  if not rows:
    warnings.append(f"{normalized_source}: candidate list が空です。")
  if status == "failed":
    warnings.append(f"{normalized_source}: status={raw_status or 'unknown'}")
  return {
    "source_type": normalized_source,
    "run_id": str(payload.get("retrieval_run_id", "") or "").strip(),
    "status": status,
    "raw_status": raw_status,
    "candidate_count": len(rows),
    "rows": rows,
    "artifact_dir": _repo_relative_path(target_dir),
    "warnings": warnings,
    "data_origin": "retrieval_artifact",
  }


def _loader_for_source(source_type: str):
  normalized_source = _normalize_source_type(source_type)
  if normalized_source == "patent":
    return load_patent_retrieval_artifact
  if normalized_source == "paper":
    return load_paper_retrieval_artifact
  return load_web_company_retrieval_artifact


def _normalize_source_type(source_type: str) -> str:
  normalized = str(source_type or "").strip().lower()
  if normalized not in SOURCE_TYPES:
    raise ValueError(f"unsupported source_type: {source_type}")
  return normalized


def _normalize_manifest_status(value: Any) -> str:
  text = str(value or "").strip().lower()
  if text == "success":
    return "success"
  if text == "partial_success":
    return "partial_success"
  return "failed"


def _retrieval_manifests_dir(base_dir: Path | str | None) -> Path:
  dirs = ensure_v9_run_dirs(Path(base_dir) if base_dir is not None else None)
  path = dirs["root"] / RETRIEVAL_MANIFEST_DIRNAME
  path.mkdir(parents=True, exist_ok=True)
  return path


def _artifact_runs_dir(base_dir: Path | str | None, source_type: str) -> Path:
  dirs = ensure_v9_run_dirs(Path(base_dir) if base_dir is not None else None)
  path = dirs["root"] / _ARTIFACT_SUBDIRS[source_type]
  path.mkdir(parents=True, exist_ok=True)
  return path


def _resolve_artifact_dir(artifact_dir: Path | str, source_type: str) -> Path:
  requested = Path(str(artifact_dir))
  if requested.is_absolute():
    resolved = requested.resolve()
    if not resolved.exists() or not resolved.is_dir():
      raise FileNotFoundError(f"artifact directory not found: {resolved}")
    return resolved
  resolved = (PROJECT_ROOT / requested).resolve()
  expected_root = _artifact_runs_dir(get_v9_runs_dir(), source_type).resolve()
  if expected_root not in {resolved, *resolved.parents}:
    raise ValueError(f"{source_type} artifact_dir が許可範囲外です: {artifact_dir}")
  if not resolved.exists() or not resolved.is_dir():
    raise FileNotFoundError(f"artifact directory not found: {resolved}")
  return resolved


def _resolve_manifest_path(manifest_path: Path | str, *, base_dir: Path | str | None) -> Path:
  manifests_dir = _retrieval_manifests_dir(base_dir).resolve()
  requested = Path(str(manifest_path))
  resolved = (PROJECT_ROOT / requested).resolve() if not requested.is_absolute() else requested.resolve()
  if manifests_dir not in {resolved, *resolved.parents}:
    raise ValueError(f"manifest path が許可範囲外です: {manifest_path}")
  if not resolved.exists():
    raise FileNotFoundError(f"manifest not found: {resolved}")
  return resolved


def _repo_relative_path(path: Path) -> str:
  try:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
  except ValueError:
    return str(path.resolve())


def _relative_artifact_dir(value: Any) -> str:
  path = Path(str(value or "").strip())
  if not str(path):
    raise ValueError("artifact_dir がありません。")
  resolved = (PROJECT_ROOT / path).resolve() if not path.is_absolute() else path.resolve()
  return _repo_relative_path(resolved)


def _load_json(path: Path) -> dict[str, Any]:
  return json.loads(path.read_text(encoding="utf-8"))


__all__ = [
  "RETRIEVAL_MANIFEST_SCHEMA_VERSION",
  "build_retrieval_run_manifest",
  "build_theme_id",
  "discover_retrieval_runs",
  "find_latest_compatible_manifest",
  "load_candidates_from_manifest",
  "load_paper_retrieval_artifact",
  "load_patent_retrieval_artifact",
  "load_retrieval_run_manifest",
  "load_web_company_retrieval_artifact",
  "save_retrieval_run_manifest",
  "stable_payload_signature",
]
