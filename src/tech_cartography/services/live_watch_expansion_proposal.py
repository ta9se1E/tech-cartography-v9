"""Rule-based watch expansion proposals from live Web Signal packs (Phase 25I)."""

from __future__ import annotations

import csv
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.runtime.live_artifact_paths import (
  check_directory_writable,
  get_live_watch_expansion_dir,
)
from tech_cartography.services.live_digest_preview import (
  find_latest_live_digest_preview_path,
  load_latest_live_digest_preview,
  load_live_digest_preview,
)
from tech_cartography.services.live_web_signal_pack import (
  find_latest_live_web_signal_pack_path,
  load_latest_live_web_signal_pack,
  load_live_web_signal_pack,
)
from tech_cartography.users.watch_profile_store import DEFAULT_COMPANIES

PROPOSAL_TYPES: frozenset[str] = frozenset(
  {
    "keyword",
    "company",
    "public_project",
    "technology_term",
    "market_application",
    "exclusion_term",
  },
)

REVIEW_STATUS = "pending_human_review"
SAFETY_LABEL = "Watch expansion proposal"

SAFETY_NOTICE = (
  "These are watch expansion proposals derived from Web Signal candidates. "
  "They are not confirmed facts and must not be used for FTO, infringement, or validity analysis. "
  "Only human-approved items may be saved to a Watch Profile Draft. "
  "Production watch profiles are never auto-updated."
)

DEFAULT_NEXT_ACTIONS: tuple[str, ...] = (
  "Review each proposal against primary sources before approval.",
  "Approve only items you want in the next monitoring scope.",
  "Rejected items remain excluded from the Watch Profile Draft.",
  "Do not treat proposals as confirmed market or legal facts.",
)

FORBIDDEN_PHRASES: tuple[str, ...] = (
  "infringement confirmed",
  "fto cleared",
  "valid patent",
  "proves infringement",
  "侵害確定",
  "有効性確定",
  "FTOクリア",
)

PUBLIC_AGENCY_TERMS: tuple[str, ...] = (
  "NEDO",
  "JST",
  "METI",
  "DOE",
  "ARPA-E",
  "EU Horizon",
  "Horizon Europe",
  "NSF",
  "経産省",
  "文部科学省",
)

TECHNOLOGY_TERMS: tuple[str, ...] = (
  "recycling",
  "precursor",
  "surface treatment",
  "PAN",
  "CFRP",
  "defect",
  "oxidation",
  "carbonization",
  "carbonisation",
  "stabilization",
  "stabilisation",
  "pre-oxidation",
  "sizing",
  "modulus",
  "tensile strength",
  "composite",
  "carbon fiber",
  "carbon fibre",
  "graphitization",
  "pyrolysis",
  "epoxy",
  "resin",
)

MARKET_APPLICATION_TERMS: tuple[str, ...] = (
  "aerospace",
  "automotive",
  "aviation",
  "wind energy",
  "wind turbine",
  "battery",
  "electric vehicle",
  "EV",
  "sports equipment",
  "construction",
  "marine",
  "hydrogen",
)

PROJECT_TERMS: tuple[str, ...] = (
  "grant",
  "project",
  "demonstration",
  "pilot",
  "consortium",
  "funding",
  "R&D program",
  "research program",
  "公募",
  "補助金",
  "national project",
)

EXCLUSION_TERMS: tuple[str, ...] = (
  "stock price",
  "earnings call",
  "quarterly results",
  "investor relations",
  "share price",
  "株価",
  "決算短信",
)

COMPANY_SUFFIX_PATTERN = re.compile(
  r"\b([A-Z][A-Za-z0-9&\-. ]{1,40}(?:Inc\.|Corp\.|Corporation|Ltd\.|LLC|AG|GmbH|S\.A\.|Co\.))\b",
)
_SENSITIVE_KEY_PATTERN = re.compile(r"(api[_-]?key|authorization|token|secret|smtp|password)", re.IGNORECASE)

_STOPWORDS = frozenset(
  {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "about",
    "into",
    "news",
    "latest",
    "update",
    "report",
  },
)


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(iso_ts: str) -> str:
  return iso_ts.replace(":", "").replace("-", "")


def _assert_no_sensitive_material(serialized: str) -> None:
  if _SENSITIVE_KEY_PATTERN.search(serialized):
    raise ValueError("Refusing to save payload containing sensitive material")
  lowered = serialized.lower()
  for phrase in FORBIDDEN_PHRASES:
    if phrase.lower() in lowered:
      raise ValueError(f"Refusing to save payload containing forbidden phrase: {phrase}")


def _normalize_key(value: str) -> str:
  return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _candidate_text(candidate: dict[str, Any]) -> str:
  return " ".join(
    [
      str(candidate.get("title") or ""),
      str(candidate.get("snippet") or ""),
      str(candidate.get("url") or ""),
    ],
  )


def _profile_values(watch_profile: dict[str, Any] | None) -> set[str]:
  if not watch_profile:
    return set()
  values: set[str] = set()
  for field in ("keywords", "companies", "countries", "clusters"):
    for item in watch_profile.get(field) or []:
      values.add(_normalize_key(str(item)))
  return values


def _new_proposal(
  *,
  proposal_type: str,
  proposed_value: str,
  reason: str,
  source_signal_ids: list[str],
  confidence_label: str,
  created_at: str,
) -> dict[str, Any]:
  cleaned = str(proposed_value or "").strip()
  if not cleaned or proposal_type not in PROPOSAL_TYPES:
    return {}
  if any(phrase.lower() in cleaned.lower() for phrase in FORBIDDEN_PHRASES):
    return {}
  return {
    "proposal_id": str(uuid.uuid4()),
    "proposal_type": proposal_type,
    "proposed_value": cleaned,
    "reason": reason.strip(),
    "source_signal_ids": list(dict.fromkeys(source_signal_ids)),
    "confidence_label": confidence_label,
    "review_status": REVIEW_STATUS,
    "safety_label": SAFETY_LABEL,
    "created_at": created_at,
  }


def _merge_proposal(
  proposals: dict[tuple[str, str], dict[str, Any]],
  proposal: dict[str, Any],
) -> None:
  if not proposal:
    return
  key = (proposal["proposal_type"], _normalize_key(proposal["proposed_value"]))
  existing = proposals.get(key)
  if existing is None:
    proposals[key] = proposal
    return
  for signal_id in proposal.get("source_signal_ids") or []:
    if signal_id not in existing["source_signal_ids"]:
      existing["source_signal_ids"].append(signal_id)
  rank = {"low": 0, "medium": 1, "high": 2}
  if rank.get(proposal["confidence_label"], 0) > rank.get(existing["confidence_label"], 0):
    existing["confidence_label"] = proposal["confidence_label"]


def _extract_terms_from_text(
  text: str,
  terms: tuple[str, ...],
  *,
  proposal_type: str,
  signal_id: str,
  confidence_label: str,
  reason_prefix: str,
  created_at: str,
) -> list[dict[str, Any]]:
  found: list[dict[str, Any]] = []
  lowered = text.lower()
  for term in terms:
    if term.lower() in lowered:
      proposal = _new_proposal(
        proposal_type=proposal_type,
        proposed_value=term,
        reason=f"{reason_prefix}: matched '{term}' in Web Signal text.",
        source_signal_ids=[signal_id],
        confidence_label=confidence_label,
        created_at=created_at,
      )
      if proposal:
        found.append(proposal)
  return found


def _extract_companies(text: str, *, signal_id: str, confidence_label: str, created_at: str) -> list[dict[str, Any]]:
  found: list[dict[str, Any]] = []
  for match in COMPANY_SUFFIX_PATTERN.findall(text):
    proposal = _new_proposal(
      proposal_type="company",
      proposed_value=match.strip(),
      reason="Rule match: company suffix pattern in Web Signal title/snippet.",
      source_signal_ids=[signal_id],
      confidence_label=confidence_label,
      created_at=created_at,
    )
    if proposal:
      found.append(proposal)
  for company in DEFAULT_COMPANIES:
    if company.lower() in text.lower():
      proposal = _new_proposal(
        proposal_type="company",
        proposed_value=company,
        reason="Rule match: known watch-list company mentioned in Web Signal.",
        source_signal_ids=[signal_id],
        confidence_label=confidence_label,
        created_at=created_at,
      )
      if proposal:
        found.append(proposal)
  return found


def _extract_keywords_from_theme(
  *,
  theme_name: str,
  query: str,
  signal_id: str,
  confidence_label: str,
  created_at: str,
) -> list[dict[str, Any]]:
  found: list[dict[str, Any]] = []
  for raw in (theme_name, query):
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9+\-/]{2,}", raw):
      if token.lower() in _STOPWORDS:
        continue
      proposal = _new_proposal(
        proposal_type="keyword",
        proposed_value=token,
        reason="Rule match: theme/query term suitable as monitoring keyword.",
        source_signal_ids=[signal_id],
        confidence_label=confidence_label,
        created_at=created_at,
      )
      if proposal:
        found.append(proposal)
  return found


def build_expansion_proposals(
  *,
  pack: dict[str, Any],
  digest: dict[str, Any] | None = None,
  theme_name: str | None = None,
  watch_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
  """Build rule-based proposals. Never auto-approves."""
  created_at = _utc_now_iso()
  resolved_theme = str(theme_name or pack.get("theme_name") or "").strip()
  existing = _profile_values(watch_profile)
  merged: dict[tuple[str, str], dict[str, Any]] = {}

  candidates = list(pack.get("candidates") or [])
  key_signals = list((digest or {}).get("key_signals") or [])
  for item in key_signals:
    if isinstance(item, dict):
      candidates.append(item)

  for candidate in candidates:
    if not isinstance(candidate, dict):
      continue
    signal_id = str(candidate.get("signal_id") or uuid.uuid4())
    text = _candidate_text(candidate)
    confidence = str(candidate.get("confidence_label") or "low")
    if confidence not in {"high", "medium", "low"}:
      confidence = "low"

    for proposal in _extract_terms_from_text(
      text,
      PUBLIC_AGENCY_TERMS,
      proposal_type="public_project",
      signal_id=signal_id,
      confidence_label=confidence,
      reason_prefix="Public agency / program signal",
      created_at=created_at,
    ):
      _merge_proposal(merged, proposal)

    for proposal in _extract_terms_from_text(
      text,
      PROJECT_TERMS,
      proposal_type="public_project",
      signal_id=signal_id,
      confidence_label=confidence,
      reason_prefix="Public project language",
      created_at=created_at,
    ):
      _merge_proposal(merged, proposal)

    for proposal in _extract_terms_from_text(
      text,
      TECHNOLOGY_TERMS,
      proposal_type="technology_term",
      signal_id=signal_id,
      confidence_label=confidence,
      reason_prefix="Technology term",
      created_at=created_at,
    ):
      _merge_proposal(merged, proposal)

    for proposal in _extract_terms_from_text(
      text,
      MARKET_APPLICATION_TERMS,
      proposal_type="market_application",
      signal_id=signal_id,
      confidence_label=confidence,
      reason_prefix="Market application term",
      created_at=created_at,
    ):
      _merge_proposal(merged, proposal)

    for proposal in _extract_terms_from_text(
      text,
      EXCLUSION_TERMS,
      proposal_type="exclusion_term",
      signal_id=signal_id,
      confidence_label="low",
      reason_prefix="Potential monitoring noise",
      created_at=created_at,
    ):
      _merge_proposal(merged, proposal)

    for proposal in _extract_companies(
      text,
      signal_id=signal_id,
      confidence_label=confidence,
      created_at=created_at,
    ):
      _merge_proposal(merged, proposal)

    if str(candidate.get("signal_type") or "") == "company_signal":
      title = str(candidate.get("title") or "").strip()
      if title:
        proposal = _new_proposal(
          proposal_type="company",
          proposed_value=title[:120],
          reason="Web Signal classified as company_signal.",
          source_signal_ids=[signal_id],
          confidence_label=confidence,
          created_at=created_at,
        )
        _merge_proposal(merged, proposal)

    for proposal in _extract_keywords_from_theme(
      theme_name=resolved_theme,
      query=str(pack.get("query") or candidate.get("query") or ""),
      signal_id=signal_id,
      confidence_label=confidence,
      created_at=created_at,
    ):
      _merge_proposal(merged, proposal)

  filtered: list[dict[str, Any]] = []
  for proposal in merged.values():
    if _normalize_key(proposal["proposed_value"]) in existing:
      continue
    filtered.append(proposal)

  filtered.sort(
    key=lambda row: (
      {"high": 0, "medium": 1, "low": 2}.get(str(row.get("confidence_label")), 3),
      str(row.get("proposal_type")),
      str(row.get("proposed_value")).lower(),
    ),
  )
  return filtered


def build_proposals_document(
  *,
  pack: dict[str, Any],
  digest: dict[str, Any] | None,
  source_pack_path: str,
  source_digest_path: str | None,
  theme_name: str,
  watch_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
  proposals = build_expansion_proposals(
    pack=pack,
    digest=digest,
    theme_name=theme_name,
    watch_profile=watch_profile,
  )
  return {
    "theme_name": theme_name,
    "source_pack_path": source_pack_path,
    "source_digest_path": source_digest_path,
    "created_at": _utc_now_iso(),
    "proposals": proposals,
    "expansion_proposals": proposals,
    "safety_notice": SAFETY_NOTICE,
    "next_actions": list(DEFAULT_NEXT_ACTIONS),
  }


def render_proposals_markdown(document: dict[str, Any]) -> str:
  lines = [
    "# Live Watch Expansion Proposals",
    "",
    f"- theme_name: {document.get('theme_name')}",
    f"- created_at: {document.get('created_at')}",
    f"- source_pack_path: {document.get('source_pack_path')}",
    f"- source_digest_path: {document.get('source_digest_path')}",
    f"- proposal_count: {len(document.get('proposals') or [])}",
    "",
    "## Safety notice",
    "",
    str(document.get("safety_notice") or SAFETY_NOTICE),
    "",
    "## Proposals",
    "",
  ]
  for item in document.get("proposals") or []:
    lines.extend(
      [
        f"### {item.get('proposal_type')}: {item.get('proposed_value')}",
        "",
        f"- proposal_id: {item.get('proposal_id')}",
        f"- confidence_label: {item.get('confidence_label')}",
        f"- review_status: {item.get('review_status')}",
        f"- safety_label: {item.get('safety_label')}",
        f"- reason: {item.get('reason')}",
        f"- source_signal_ids: {', '.join(item.get('source_signal_ids') or [])}",
        "",
      ],
    )
  return "\n".join(lines).strip() + "\n"


def save_live_watch_expansion_proposals(
  document: dict[str, Any],
  output_root: Path | str,
) -> dict[str, str]:
  out_dir = get_live_watch_expansion_dir(output_root)
  writable, message = check_directory_writable(out_dir)
  if not writable:
    raise ValueError(message or f"Cannot write watch expansion proposals to {out_dir}")

  created_at = str(document.get("created_at") or _utc_now_iso())
  slug = _timestamp_slug(created_at)
  json_path = out_dir / f"live_watch_expansion_proposals_{slug}.json"
  csv_path = out_dir / f"live_watch_expansion_proposals_{slug}.csv"
  md_path = out_dir / f"live_watch_expansion_proposals_{slug}.md"

  serialized = json.dumps(document, indent=2, ensure_ascii=False)
  _assert_no_sensitive_material(serialized)
  json_path.write_text(serialized + "\n", encoding="utf-8")

  proposals = document.get("proposals") or []
  if proposals:
    fieldnames = list(proposals[0].keys())
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
      writer = csv.DictWriter(handle, fieldnames=fieldnames)
      writer.writeheader()
      writer.writerows(proposals)
  else:
    csv_path.write_text("", encoding="utf-8")

  md_path.write_text(render_proposals_markdown(document), encoding="utf-8")
  return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}


def find_latest_live_watch_expansion_proposals_path(output_root: Path | str) -> Path | None:
  out_dir = get_live_watch_expansion_dir(output_root)
  if not out_dir.exists():
    return None
  files = sorted(
    out_dir.glob("live_watch_expansion_proposals_*.json"),
    key=lambda path: path.stat().st_mtime,
    reverse=True,
  )
  return files[0] if files else None


def load_live_watch_expansion_proposals(path: Path | str) -> dict[str, Any] | None:
  target = Path(path)
  if not target.exists():
    return None
  try:
    data = json.loads(target.read_text(encoding="utf-8"))
  except (json.JSONDecodeError, OSError):
    return None
  return data if isinstance(data, dict) else None


def load_latest_live_watch_expansion_proposals(output_root: Path | str) -> dict[str, Any] | None:
  latest = find_latest_live_watch_expansion_proposals_path(output_root)
  if latest is None:
    return None
  return load_live_watch_expansion_proposals(latest)


def create_live_watch_expansion_proposals_from_latest(
  *,
  output_root: Path | str,
  theme_name: str | None = None,
  watch_profile: dict[str, Any] | None = None,
  login_required: bool,
  is_authenticated: bool,
  auth_role: str,
) -> dict[str, Any]:
  """Generate and save proposals from latest live artifacts. Never auto-approves."""
  if login_required and not is_authenticated:
    return {"ok": False, "error": "login_required", "message": "ログイン後に実行できます。"}
  if login_required and str(auth_role or "member") != "admin":
    return {"ok": False, "error": "admin_required", "message": "管理者のみ実行できます。"}

  pack_path = find_latest_live_web_signal_pack_path(output_root)
  if pack_path is None:
    return {
      "ok": False,
      "error": "missing_source_pack",
      "message": "latest live_web_signal_pack がありません。先に Web Signal Pack を作成してください。",
    }

  pack = load_live_web_signal_pack(pack_path)
  if not pack:
    return {
      "ok": False,
      "error": "invalid_source_pack",
      "message": "source pack の読み込みに失敗しました。",
    }

  digest_path = find_latest_live_digest_preview_path(output_root)
  digest = load_latest_live_digest_preview(output_root) if digest_path else None
  resolved_theme = str(theme_name or pack.get("theme_name") or "").strip()

  document = build_proposals_document(
    pack=pack,
    digest=digest,
    source_pack_path=str(pack_path),
    source_digest_path=str(digest_path) if digest_path else None,
    theme_name=resolved_theme,
    watch_profile=watch_profile,
  )

  try:
    saved_paths = save_live_watch_expansion_proposals(document, output_root)
  except (OSError, ValueError) as exc:
    return {"ok": False, "error": "save_failed", "message": str(exc)}

  return {
    "ok": True,
    "error": None,
    "message": f"監視範囲拡張候補を {len(document.get('proposals') or [])} 件作成しました（承認前）。",
    "document": document,
    "saved_paths": saved_paths,
    "source_pack_path": str(pack_path),
    "source_digest_path": str(digest_path) if digest_path else None,
  }
