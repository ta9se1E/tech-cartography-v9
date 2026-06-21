"""Human-approved Watch Profile Draft storage (Phase 25I)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.runtime.live_artifact_paths import (
  check_directory_writable,
  get_live_watch_profiles_dir,
)
from tech_cartography.services.live_watch_expansion_proposal import (
  FORBIDDEN_PHRASES,
  PROPOSAL_TYPES,
)

DRAFT_SAFETY_NOTICE = (
  "This Watch Profile Draft contains human-approved monitoring scope suggestions only. "
  "It does not update production watch profiles automatically. "
  "Items remain Web Signal-derived proposals — not confirmed facts. "
  "Not for FTO, infringement, or validity analysis."
)

_APPROVED_FIELD_BY_TYPE: dict[str, str] = {
  "keyword": "approved_keywords",
  "company": "approved_companies",
  "public_project": "approved_public_projects",
  "technology_term": "approved_technology_terms",
  "market_application": "approved_market_applications",
}


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(iso_ts: str) -> str:
  return iso_ts.replace(":", "").replace("-", "")


def _assert_no_sensitive_material(serialized: str) -> None:
  lowered = serialized.lower()
  if "smtp_password" in lowered or "api_key" in lowered:
    raise ValueError("Refusing to save draft containing sensitive material")
  for phrase in FORBIDDEN_PHRASES:
    if phrase.lower() in lowered:
      raise ValueError(f"Refusing to save draft containing forbidden phrase: {phrase}")


def build_next_monitoring_query_candidates(draft: dict[str, Any]) -> list[str]:
  parts: list[str] = []
  for field in (
    "approved_keywords",
    "approved_technology_terms",
    "approved_companies",
    "approved_market_applications",
  ):
    for item in draft.get(field) or []:
      token = str(item).strip()
      if token and token not in parts:
        parts.append(token)
  if not parts:
    return []
  theme = str(draft.get("theme_name") or "monitoring theme").strip()
  joined = " ".join(parts[:5])
  return [
    f"{theme} {joined} patent intelligence",
    f"{joined} carbon fiber watch query",
  ]


def build_watch_profile_draft_from_decisions(
  *,
  proposals_document: dict[str, Any],
  approved_proposal_ids: list[str],
  rejected_proposal_ids: list[str],
  approved_by: str,
  source_proposal_path: str,
) -> dict[str, Any]:
  """Build draft from explicit human decisions. Never auto-approves all proposals."""
  approved_ids = {str(item) for item in approved_proposal_ids}
  rejected_ids = {str(item) for item in rejected_proposal_ids}
  overlap = approved_ids & rejected_ids
  if overlap:
    raise ValueError("A proposal cannot be both approved and rejected")

  proposals = proposals_document.get("proposals") or proposals_document.get("expansion_proposals") or []
  by_id = {str(row.get("proposal_id")): row for row in proposals if isinstance(row, dict)}

  draft: dict[str, Any] = {
    "theme_name": str(proposals_document.get("theme_name") or ""),
    "approved_keywords": [],
    "approved_companies": [],
    "approved_public_projects": [],
    "approved_technology_terms": [],
    "approved_market_applications": [],
    "rejected_items": [],
    "approved_by": str(approved_by or "admin"),
    "approved_at": _utc_now_iso(),
    "source_proposal_path": source_proposal_path,
    "safety_notice": DRAFT_SAFETY_NOTICE,
    "next_monitoring_query_candidates": [],
  }

  for proposal_id in approved_ids:
    proposal = by_id.get(proposal_id)
    if not proposal:
      continue
    proposal_type = str(proposal.get("proposal_type") or "")
    if proposal_type not in PROPOSAL_TYPES:
      continue
    if proposal_type == "exclusion_term":
      draft["rejected_items"].append(
        {
          "proposal_id": proposal_id,
          "proposal_type": proposal_type,
          "proposed_value": proposal.get("proposed_value"),
          "reason": "Approved as exclusion/noise term — kept out of active watch lists.",
        },
      )
      continue
    field = _APPROVED_FIELD_BY_TYPE.get(proposal_type)
    if not field:
      continue
    value = str(proposal.get("proposed_value") or "").strip()
    if value and value not in draft[field]:
      draft[field].append(value)

  for proposal_id in rejected_ids:
    proposal = by_id.get(proposal_id)
    if not proposal:
      continue
    draft["rejected_items"].append(
      {
        "proposal_id": proposal_id,
        "proposal_type": proposal.get("proposal_type"),
        "proposed_value": proposal.get("proposed_value"),
        "reason": "Rejected by human reviewer.",
      },
    )

  draft["next_monitoring_query_candidates"] = build_next_monitoring_query_candidates(draft)
  return draft


def render_watch_profile_draft_markdown(draft: dict[str, Any]) -> str:
  lines = [
    "# Watch Profile Draft (Human Approved)",
    "",
    f"- theme_name: {draft.get('theme_name')}",
    f"- approved_by: {draft.get('approved_by')}",
    f"- approved_at: {draft.get('approved_at')}",
    f"- source_proposal_path: {draft.get('source_proposal_path')}",
    "",
    "## Approved scope",
    "",
  ]
  for label in (
    "approved_keywords",
    "approved_companies",
    "approved_public_projects",
    "approved_technology_terms",
    "approved_market_applications",
  ):
    items = draft.get(label) or []
    lines.append(f"### {label}")
    lines.append("")
    if items:
      for item in items:
        lines.append(f"- {item}")
    else:
      lines.append("- (none)")
    lines.append("")

  lines.extend(
    [
      "## Next monitoring query candidates",
      "",
    ],
  )
  for query in draft.get("next_monitoring_query_candidates") or []:
    lines.append(f"- {query}")
  lines.extend(
    [
      "",
      "## Safety notice",
      "",
      str(draft.get("safety_notice") or DRAFT_SAFETY_NOTICE),
      "",
    ],
  )
  return "\n".join(lines).strip() + "\n"


def save_watch_profile_draft(
  draft: dict[str, Any],
  output_root: Path | str,
) -> dict[str, str]:
  out_dir = get_live_watch_profiles_dir(output_root)
  writable, message = check_directory_writable(out_dir)
  if not writable:
    raise ValueError(message or f"Cannot write watch profile draft to {out_dir}")

  approved_at = str(draft.get("approved_at") or _utc_now_iso())
  slug = _timestamp_slug(approved_at)
  json_path = out_dir / f"watch_profile_draft_{slug}.json"
  md_path = out_dir / f"watch_profile_draft_{slug}.md"

  serialized = json.dumps(draft, indent=2, ensure_ascii=False)
  _assert_no_sensitive_material(serialized)
  json_path.write_text(serialized + "\n", encoding="utf-8")
  md_path.write_text(render_watch_profile_draft_markdown(draft), encoding="utf-8")
  return {"json": str(json_path), "markdown": str(md_path)}


WATCH_PROFILE_DRAFT_GLOB = "watch_profile_draft_*.json"
WATCH_PROFILE_DRAFT_PREFIX = "watch_profile_draft_"


def _draft_filename_slug(path: Path) -> str:
  name = path.name
  if name.startswith(WATCH_PROFILE_DRAFT_PREFIX) and name.endswith(".json"):
    return name[len(WATCH_PROFILE_DRAFT_PREFIX) : -5]
  return name


def _draft_path_sort_key(path: Path) -> tuple[str, float]:
  slug = _draft_filename_slug(path)
  try:
    mtime = float(path.stat().st_mtime)
  except OSError:
    mtime = 0.0
  return slug, mtime


def iter_watch_profile_draft_search_dirs(project_root: Path | str | None = None) -> list[Path]:
  """Primary LIVE_OUTPUTS_ROOT dir plus local outputs fallback when different."""
  primary = get_live_watch_profiles_dir(project_root)
  directories = [primary]
  if project_root is not None:
    fallback = Path(project_root).resolve() / "outputs" / "live_watch_profiles"
    if fallback not in directories:
      directories.append(fallback)
  return directories


def list_watch_profile_draft_json_paths(project_root: Path | str | None = None) -> list[Path]:
  """List draft JSON files only (never .md). Search all configured dirs."""
  found: list[Path] = []
  seen: set[str] = set()
  for directory in iter_watch_profile_draft_search_dirs(project_root):
    try:
      if not directory.is_dir():
        continue
      for path in directory.glob(WATCH_PROFILE_DRAFT_GLOB):
        if path.suffix.lower() != ".json":
          continue
        key = str(path.resolve())
        if key in seen:
          continue
        seen.add(key)
        found.append(path)
    except OSError:
      continue
  return found


def find_latest_watch_profile_draft_path(output_root: Path | str | None = None) -> Path | None:
  paths = list_watch_profile_draft_json_paths(output_root)
  if not paths:
    return None
  return max(paths, key=_draft_path_sort_key)


def load_watch_profile_draft(path: Path | str) -> dict[str, Any] | None:
  draft, status, _message = load_watch_profile_draft_with_status(path)
  if status == "ok":
    return draft
  return None


def load_watch_profile_draft_with_status(
  path: Path | str,
) -> tuple[dict[str, Any] | None, str, str | None]:
  """Return (draft, load_status, message). Never raises."""
  target = Path(path)
  if not target.exists():
    return None, "missing", f"draft file not found: {target}"
  if target.suffix.lower() != ".json":
    return None, "read_error", f"expected JSON draft file: {target}"
  try:
    raw = target.read_text(encoding="utf-8")
  except OSError as exc:
    return None, "read_error", f"cannot read draft file ({type(exc).__name__})"
  try:
    data = json.loads(raw)
  except json.JSONDecodeError as exc:
    return None, "parse_error", f"invalid JSON in draft file ({exc.msg})"
  if not isinstance(data, dict):
    return None, "parse_error", "draft JSON root must be an object"
  return data, "ok", None


def describe_watch_profile_draft_storage(project_root: Path | str | None = None) -> dict[str, Any]:
  """Admin-safe storage summary for Watch Profile Draft visibility."""
  from tech_cartography.runtime.live_artifact_paths import (
    LIVE_OUTPUTS_ROOT_ENV,
    get_live_outputs_root,
    using_live_outputs_root_env,
  )

  search_dirs = [str(path) for path in iter_watch_profile_draft_search_dirs(project_root)]
  json_paths = list_watch_profile_draft_json_paths(project_root)
  latest_path = find_latest_watch_profile_draft_path(project_root)
  env_value = str(os.environ.get(LIVE_OUTPUTS_ROOT_ENV, "") or "").strip()

  status = "missing"
  message: str | None = "no watch_profile_draft JSON files found"
  draft: dict[str, Any] | None = None
  if latest_path is not None:
    draft, status, message = load_watch_profile_draft_with_status(latest_path)

  return {
    "live_outputs_root_env": env_value or "(unset — local outputs fallback)",
    "using_env_override": using_live_outputs_root_env(),
    "active_storage_root": str(get_live_outputs_root(project_root)),
    "live_watch_profiles_dirs": search_dirs,
    "draft_file_count": len(json_paths),
    "latest_draft_path": str(latest_path) if latest_path else None,
    "load_status": status,
    "load_message": message,
    "draft": draft,
  }


def resolve_watch_profile_draft_status(project_root: Path | str | None = None) -> dict[str, Any]:
  """Resolved latest draft plus load diagnostics for UI."""
  info = describe_watch_profile_draft_storage(project_root)
  return {
    "draft": info.get("draft"),
    "latest_path": info.get("latest_draft_path"),
    "load_status": info.get("load_status"),
    "load_message": info.get("load_message"),
    "draft_file_count": info.get("draft_file_count", 0),
    "live_watch_profiles_dirs": info.get("live_watch_profiles_dirs") or [],
    "live_outputs_root_env": info.get("live_outputs_root_env"),
    "using_env_override": info.get("using_env_override"),
    "active_storage_root": info.get("active_storage_root"),
  }


def load_latest_watch_profile_draft(output_root: Path | str | None = None) -> dict[str, Any] | None:
  latest = find_latest_watch_profile_draft_path(output_root)
  if latest is None:
    return None
  draft, status, _message = load_watch_profile_draft_with_status(latest)
  if status == "ok":
    return draft
  return None


def load_latest_watch_profile_draft_with_path(
  output_root: Path | str | None = None,
) -> tuple[dict[str, Any] | None, Path | None, str, str | None]:
  latest = find_latest_watch_profile_draft_path(output_root)
  if latest is None:
    return None, None, "missing", "no watch_profile_draft JSON files found"
  draft, status, message = load_watch_profile_draft_with_status(latest)
  return draft, latest, status, message


def apply_human_watch_expansion_decisions(
  *,
  proposals_document: dict[str, Any],
  approved_proposal_ids: list[str],
  rejected_proposal_ids: list[str],
  approved_by: str,
  source_proposal_path: str,
  output_root: Path | str,
) -> dict[str, Any]:
  """Persist human-approved draft only — never touches production watch profile store."""
  if not approved_proposal_ids and not rejected_proposal_ids:
    return {
      "ok": False,
      "error": "empty_selection",
      "message": "承認または却下する proposal を選択してください。",
    }

  try:
    draft = build_watch_profile_draft_from_decisions(
      proposals_document=proposals_document,
      approved_proposal_ids=approved_proposal_ids,
      rejected_proposal_ids=rejected_proposal_ids,
      approved_by=approved_by,
      source_proposal_path=source_proposal_path,
    )
    saved_paths = save_watch_profile_draft(draft, output_root)
  except (OSError, ValueError) as exc:
    return {"ok": False, "error": "save_failed", "message": str(exc)}

  return {
    "ok": True,
    "error": None,
    "message": "Watch Profile Draft を保存しました（本番 profile は未更新）。",
    "draft": draft,
    "saved_paths": saved_paths,
  }
