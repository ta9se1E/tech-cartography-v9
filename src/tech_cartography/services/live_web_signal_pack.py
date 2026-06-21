"""Convert live Tavily search hits into Web Signal candidate packs (Phase 25E)."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from tech_cartography.runtime.live_artifact_paths import (
  check_directory_writable,
  get_live_web_signals_dir,
)
from tech_cartography.services.live_tavily_search import (
  PROVIDER,
  clamp_max_results,
  run_live_tavily_search_smoke,
)
from tech_cartography.web_signals.schema import extract_source_domain, new_signal_id

LIVE_SIGNAL_TYPES: frozenset[str] = frozenset(
  {
    "company_signal",
    "public_project_signal",
    "market_signal",
    "research_signal",
    "unknown",
  },
)

CONFIDENCE_LABELS: frozenset[str] = frozenset({"high", "medium", "low"})
REVIEW_STATUS = "needs_human_review"
SAFETY_LABEL = "Web Signal candidate"
SOURCE_TYPE_LIVE = "live_web_signal_pack"

SAFETY_NOTICE = (
  "These are Web Signal candidates for human review. "
  "They do not prove direct relationship, legal status, infringement, validity, or market truth."
)

DEFAULT_NEXT_ACTIONS: tuple[str, ...] = (
  "Review each candidate against primary sources before use.",
  "Do not treat candidates as confirmed market or legal facts.",
  "Link promising candidates to patent / claim context in a later phase.",
)

_SENSITIVE_KEY_PATTERN = re.compile(r"(api[_-]?key|authorization|token|secret)", re.IGNORECASE)


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(iso_ts: str) -> str:
  return iso_ts.replace(":", "").replace("-", "")


def infer_live_signal_type(*, title: str, snippet: str, url: str) -> str:
  text = f"{title} {snippet}".lower()
  domain = extract_source_domain(url)

  public_keywords = (
    "grant",
    "公募",
    "補助金",
    "nedo",
    "jst",
    "national project",
    "research project",
    "public project",
    "政府",
    "国プロ",
  )
  if any(keyword in text for keyword in public_keywords):
    return "public_project_signal"
  if domain.endswith(".go.jp") or "gov" in domain:
    return "public_project_signal"

  company_keywords = (
    "company",
    "corp",
    "corporation",
    "press release",
    "プレスリリース",
    "investor",
    "ir ",
    "決算",
    "enterprise",
    "企業",
  )
  if any(keyword in text for keyword in company_keywords) or "/ir/" in url.lower():
    return "company_signal"

  market_keywords = ("market", "industry", "demand", "forecast", "市場", "需要", "シェア")
  if any(keyword in text for keyword in market_keywords):
    return "market_signal"

  research_keywords = (
    "research",
    "university",
    "paper",
    "patent",
    "study",
    "journal",
    "論文",
    "研究",
    "特許",
  )
  if any(keyword in text for keyword in research_keywords):
    return "research_signal"

  return "unknown"


def infer_confidence_label(score: Any) -> str:
  try:
    value = float(score)
  except (TypeError, ValueError):
    return "low"
  if value >= 0.8:
    return "high"
  if value >= 0.5:
    return "medium"
  return "low"


def tavily_results_to_candidates(
  *,
  theme_name: str,
  query: str,
  results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
  candidates: list[dict[str, Any]] = []
  for item in results:
    title = str(item.get("title") or "").strip()
    url = str(item.get("url") or "").strip()
    snippet = str(item.get("snippet") or item.get("content") or "").strip()
    fetched_at = str(item.get("fetched_at") or _utc_now_iso())
    score = item.get("score")
    candidates.append(
      {
        "signal_id": new_signal_id(),
        "theme_name": theme_name,
        "query": query,
        "title": title,
        "url": url,
        "snippet": snippet,
        "score": score,
        "provider": PROVIDER,
        "signal_type": infer_live_signal_type(title=title, snippet=snippet, url=url),
        "confidence_label": infer_confidence_label(score),
        "review_status": REVIEW_STATUS,
        "safety_label": SAFETY_LABEL,
        "fetched_at": fetched_at,
      },
    )
  return candidates


def build_live_web_signal_pack(
  *,
  theme_name: str,
  query: str,
  candidates: list[dict[str, Any]],
  fetched_at: str | None = None,
  provider: str = PROVIDER,
  next_actions: list[str] | None = None,
) -> dict[str, Any]:
  return {
    "theme_name": theme_name,
    "source_type": SOURCE_TYPE_LIVE,
    "query": query,
    "fetched_at": fetched_at or _utc_now_iso(),
    "provider": provider,
    "candidates": candidates,
    "safety_notice": SAFETY_NOTICE,
    "next_actions": list(next_actions or DEFAULT_NEXT_ACTIONS),
  }


def _assert_no_api_key_material(serialized: str) -> None:
  lowered = serialized.lower()
  if "tavily_api_key" in lowered or '"api_key"' in lowered:
    raise ValueError("Refusing to save payload containing API key material")


def render_live_web_signal_pack_markdown(pack: dict[str, Any]) -> str:
  lines = [
    "# Live Web Signal Pack",
    "",
    f"- theme_name: {pack.get('theme_name')}",
    f"- query: {pack.get('query')}",
    f"- provider: {pack.get('provider')}",
    f"- fetched_at: {pack.get('fetched_at')}",
    f"- candidate_count: {len(pack.get('candidates') or [])}",
    "",
    "## Safety notice",
    "",
    str(pack.get("safety_notice") or SAFETY_NOTICE),
    "",
    "## Next actions",
    "",
  ]
  for action in pack.get("next_actions") or []:
    lines.append(f"- {action}")
  lines.extend(["", "## Candidates", ""])
  for index, item in enumerate(pack.get("candidates") or [], start=1):
    lines.extend(
      [
        f"### {index}. {item.get('title') or '(no title)'}",
        "",
        f"- signal_id: {item.get('signal_id')}",
        f"- url: {item.get('url')}",
        f"- signal_type: {item.get('signal_type')}",
        f"- confidence_label: {item.get('confidence_label')}",
        f"- review_status: {item.get('review_status')}",
        f"- safety_label: {item.get('safety_label')}",
        "",
        str(item.get("snippet") or ""),
        "",
      ],
    )
  return "\n".join(lines).strip() + "\n"


def save_live_web_signal_pack(
  pack: dict[str, Any],
  output_root: Path | str,
) -> dict[str, str]:
  out_dir = get_live_web_signals_dir(output_root)
  writable, message = check_directory_writable(out_dir)
  if not writable:
    raise ValueError(message or f"Cannot write live web signal pack to {out_dir}")

  fetched_at = str(pack.get("fetched_at") or _utc_now_iso())
  slug = _timestamp_slug(fetched_at)
  json_path = out_dir / f"live_web_signal_pack_{slug}.json"
  csv_path = out_dir / f"live_web_signal_pack_{slug}.csv"
  md_path = out_dir / f"live_web_signal_pack_{slug}.md"

  serialized = json.dumps(pack, indent=2, ensure_ascii=False)
  _assert_no_api_key_material(serialized)
  json_path.write_text(serialized + "\n", encoding="utf-8")

  candidates = pack.get("candidates") or []
  if candidates:
    fieldnames = list(candidates[0].keys())
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
      writer = csv.DictWriter(handle, fieldnames=fieldnames)
      writer.writeheader()
      writer.writerows(candidates)
  else:
    csv_path.write_text("", encoding="utf-8")

  md_path.write_text(render_live_web_signal_pack_markdown(pack), encoding="utf-8")
  return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}


def live_web_signals_dir(output_root: Path | str) -> Path:
  return get_live_web_signals_dir(output_root)


def find_latest_live_web_signal_pack_path(output_root: Path | str) -> Path | None:
  out_dir = live_web_signals_dir(output_root)
  if not out_dir.exists():
    return None
  candidates = sorted(out_dir.glob("live_web_signal_pack_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
  return candidates[0] if candidates else None


def load_live_web_signal_pack(path: Path | str) -> dict[str, Any] | None:
  target = Path(path)
  if not target.exists():
    return None
  try:
    data = json.loads(target.read_text(encoding="utf-8"))
  except (json.JSONDecodeError, OSError):
    return None
  return data if isinstance(data, dict) else None


def load_latest_live_web_signal_pack(output_root: Path | str) -> dict[str, Any] | None:
  latest = find_latest_live_web_signal_pack_path(output_root)
  if latest is None:
    return None
  return load_live_web_signal_pack(latest)


def run_live_web_signal_pack(
  *,
  theme_name: str,
  query: str,
  max_results: int = 3,
  login_required: bool,
  is_authenticated: bool,
  auth_role: str,
  output_root: Path | str,
  post_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
  """Search Tavily, convert to candidates, save pack. Never raises."""
  cleaned_theme = str(theme_name or "").strip()
  cleaned_query = str(query or "").strip()
  if not cleaned_theme:
    return {
      "ok": False,
      "error": "empty_theme",
      "message": "theme_name を入力してください。",
      "candidates": [],
      "pack": None,
      "saved_paths": {},
    }
  if not cleaned_query:
    return {
      "ok": False,
      "error": "empty_query",
      "message": "検索クエリを入力してください。",
      "candidates": [],
      "pack": None,
      "saved_paths": {},
    }

  bounded = clamp_max_results(max_results)
  search_result = run_live_tavily_search_smoke(
    cleaned_query,
    max_results=bounded,
    login_required=login_required,
    is_authenticated=is_authenticated,
    auth_role=auth_role,
    post_fn=post_fn,
  )
  if not search_result.get("ok"):
    return {
      **search_result,
      "candidates": [],
      "pack": None,
    }

  candidates = tavily_results_to_candidates(
    theme_name=cleaned_theme,
    query=cleaned_query,
    results=search_result.get("results") or [],
  )
  pack = build_live_web_signal_pack(
    theme_name=cleaned_theme,
    query=cleaned_query,
    candidates=candidates,
    fetched_at=str(search_result.get("fetched_at") or _utc_now_iso()),
  )
  try:
    saved_paths = save_live_web_signal_pack(pack, output_root)
  except (OSError, ValueError) as exc:
    return {
      "ok": False,
      "error": "save_failed",
      "message": f"Web Signal Pack 保存に失敗しました: {exc}",
      "candidates": candidates,
      "pack": pack,
      "saved_paths": {},
    }

  return {
    "ok": True,
    "error": None,
    "message": f"Web Signal Pack を作成しました（{len(candidates)} 件）",
    "query": cleaned_query,
    "theme_name": cleaned_theme,
    "provider": PROVIDER,
    "fetched_at": pack["fetched_at"],
    "max_results": bounded,
    "candidates": candidates,
    "pack": pack,
    "saved_paths": saved_paths,
    "safety_notice": SAFETY_NOTICE,
    "next_actions": pack["next_actions"],
  }
