"""Web Signal evidence review for Digest Preview integration (Phase 25U)."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.runtime.live_artifact_paths import (
  check_directory_writable,
  get_live_web_signals_dir,
)
from tech_cartography.services.live_run_history import (
  attach_user_run_metadata,
  generate_run_id,
  record_live_run,
)
from tech_cartography.services.live_web_signal_artifact_reader import (
  read_latest_web_signal_artifact_summary,
)

ACTION_TYPE = "live_web_signal_review"
DIGEST_WITH_SIGNALS_ACTION = "live_digest_preview_with_web_signals"

CANDIDATE_ONLY_NOTICE = (
  "Web Signal entries are candidate information only — not confirmed facts. "
  "Not for FTO, infringement, validity, or legal judgement."
)

CANDIDATE_ONLY_NOTICE_JA = (
  "Web Signal は候補情報であり確定事実ではありません。"
  "FTO、侵害、有効性判断ではありません。"
)

_SENSITIVE_PATTERN = re.compile(
  r"(smtp_password|tavily_api_key|api[_-]?key\s*[:=]|authorization|oauth|jwt)",
  re.IGNORECASE,
)


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(iso_ts: str) -> str:
  return iso_ts.replace(":", "").replace("-", "")


def _safety_flags() -> dict[str, bool]:
  return {
    "technical_validation": False,
    "legal_judgement": False,
    "fto_judgement": False,
    "infringement_judgement": False,
    "validity_judgement": False,
    "candidate_information_only": True,
    "no_external_api_call": True,
    "no_email_send": True,
    "no_scheduler_start": True,
  }


def _domain_summary(signals: list[dict[str, Any]]) -> dict[str, int]:
  counts: dict[str, int] = {}
  for signal in signals:
    domain = str(signal.get("domain") or "unknown").strip() or "unknown"
    counts[domain] = counts.get(domain, 0) + 1
  return dict(sorted(counts.items(), key=lambda row: (-row[1], row[0])))


def _duplicate_url_count(signals: list[dict[str, Any]]) -> int:
  urls = [str(s.get("url") or "").strip().lower() for s in signals if str(s.get("url") or "").strip()]
  return max(0, len(urls) - len(set(urls)))


def _missing_date_count(signals: list[dict[str, Any]]) -> int:
  return sum(1 for s in signals if not s.get("published_date"))


def _top_candidates(signals: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
  top: list[dict[str, Any]] = []
  for signal in signals[:limit]:
    top.append(
      {
        "title": signal.get("title"),
        "url": signal.get("url"),
        "domain": signal.get("domain"),
        "query": signal.get("query"),
        "confidence_label": signal.get("confidence_label") or "candidate",
        "snippet": signal.get("snippet"),
      },
    )
  return top


def _caution_notes(summary: dict[str, Any]) -> list[str]:
  notes = [
    CANDIDATE_ONLY_NOTICE_JA,
    "原典 URL を開いて人間が確認してください。",
  ]
  if not summary.get("artifact_exists"):
    notes.insert(0, "Web Signal候補はまだ収集されていません。")
  elif summary.get("status") != "success":
    notes.insert(0, f"最新 artifact status={summary.get('status')} — 成功収集分のみ Digest に反映してください。")
  if _duplicate_url_count(summary.get("web_signals") or []) > 0:
    notes.append("重複 URL が含まれています。統合前に確認してください。")
  if _missing_date_count(summary.get("web_signals") or []) > 0:
    notes.append("公開日が欠落している候補があります。")
  return notes


def build_web_signal_review(
  output_root: Path | str,
  *,
  source_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
  """Build review model from latest artifact. No external API calls."""
  summary = source_summary or read_latest_web_signal_artifact_summary(output_root)
  signals = list(summary.get("web_signals") or [])
  return {
    "review_id": f"wsr-{uuid.uuid4().hex[:12]}",
    "source_artifact_path": summary.get("artifact_path"),
    "theme_name": summary.get("theme_name"),
    "total_signal_count": int(summary.get("result_count") or len(signals)),
    "queries_used": list(summary.get("queries_used") or []),
    "signals_by_domain": _domain_summary(signals),
    "top_candidate_signals": _top_candidates(signals),
    "duplicate_url_count": _duplicate_url_count(signals),
    "missing_date_count": _missing_date_count(signals),
    "caution_notes": _caution_notes(summary),
    "candidate_only_notice": CANDIDATE_ONLY_NOTICE,
    "candidate_only_notice_ja": CANDIDATE_ONLY_NOTICE_JA,
    "safety_flags": _safety_flags(),
    "artifact_status": summary.get("status"),
    "artifact_exists": bool(summary.get("artifact_exists")),
    "created_at": _utc_now_iso(),
  }


def render_web_signal_section_markdown(review: dict[str, Any]) -> str:
  lines = [
    "## Web Signal候補",
    "",
    f"> {review.get('candidate_only_notice_ja')}",
    "",
  ]
  if not review.get("artifact_exists"):
    lines.append("Web Signal候補はまだ収集されていません。")
    return "\n".join(lines).strip() + "\n"

  lines.extend(
    [
      f"- source artifact path: {review.get('source_artifact_path')}",
      f"- result_count: {review.get('total_signal_count')}",
      f"- queries_used: {', '.join(review.get('queries_used') or []) or '(none)'}",
      "",
      "### domain summary",
      "",
    ],
  )
  domain_counts = review.get("signals_by_domain") or {}
  if domain_counts:
    for domain, count in domain_counts.items():
      lines.append(f"- {domain}: {count}")
  else:
    lines.append("_（domain なし）_")

  lines.extend(["", "### top candidate signals", ""])
  top = review.get("top_candidate_signals") or []
  if not top:
    lines.append("_（候補なし）_")
  for index, signal in enumerate(top, start=1):
    lines.extend(
      [
        f"{index}. **{signal.get('title') or '(no title)'}** (`{signal.get('confidence_label')}`)",
        f"   - url: {signal.get('url')}",
        f"   - domain: {signal.get('domain')}",
        f"   - query: {signal.get('query')}",
        "",
      ],
    )

  lines.extend(["### caution notes", ""])
  for note in review.get("caution_notes") or []:
    lines.append(f"- {note}")
  lines.append("")
  lines.append(f"_{review.get('candidate_only_notice')}_")
  return "\n".join(lines).strip() + "\n"


def render_web_signal_section_plain(review: dict[str, Any]) -> str:
  lines = ["=== Web Signal候補 ===", str(review.get("candidate_only_notice_ja")), ""]
  if not review.get("artifact_exists"):
    lines.append("Web Signal候補はまだ収集されていません。")
    return "\n".join(lines).strip() + "\n"

  lines.extend(
    [
      f"source artifact path: {review.get('source_artifact_path')}",
      f"result_count: {review.get('total_signal_count')}",
      f"queries_used: {', '.join(review.get('queries_used') or []) or '(none)'}",
      "",
      "--- domain summary ---",
    ],
  )
  for domain, count in (review.get("signals_by_domain") or {}).items():
    lines.append(f"- {domain}: {count}")
  lines.extend(["", "--- top candidate signals ---"])
  for index, signal in enumerate(review.get("top_candidate_signals") or [], start=1):
    lines.append(
      f"{index}. {signal.get('title')} [{signal.get('confidence_label')}] {signal.get('url')}",
    )
  lines.extend(["", "--- caution notes ---"])
  for note in review.get("caution_notes") or []:
    lines.append(f"- {note}")
  return "\n".join(lines).strip() + "\n"


def _assert_safe_serialized(serialized: str) -> None:
  scrubbed = re.sub(
    r"(TAVILY_API_KEY|OPENAI_API_KEY|SMTP_PASSWORD)",
    "[env-name-redacted]",
    serialized,
    flags=re.IGNORECASE,
  )
  if _SENSITIVE_PATTERN.search(scrubbed):
    raise ValueError("Refusing to save web signal review containing sensitive material")


def save_web_signal_review(
  review: dict[str, Any],
  output_root: Path | str,
) -> dict[str, str]:
  out_dir = get_live_web_signals_dir(output_root)
  writable, message = check_directory_writable(out_dir)
  if not writable:
    raise ValueError(message or f"Cannot write web signal review to {out_dir}")

  created_at = str(review.get("created_at") or _utc_now_iso())
  slug = _timestamp_slug(created_at)
  review_id = str(review.get("review_id") or f"wsr-{uuid.uuid4().hex[:12]}")
  json_path = out_dir / f"live_web_signal_review_{slug}_{review_id}.json"
  md_path = out_dir / f"live_web_signal_review_{slug}_{review_id}.md"
  serialized = json.dumps(review, indent=2, ensure_ascii=False)
  _assert_safe_serialized(serialized)
  json_path.write_text(serialized + "\n", encoding="utf-8")
  md_path.write_text(render_web_signal_section_markdown(review), encoding="utf-8")
  return {"json": str(json_path), "markdown": str(md_path)}


def record_web_signal_review_run(
  *,
  review: dict[str, Any],
  output_root: Path | str,
  user_context: dict[str, Any] | None = None,
  saved_paths: dict[str, str] | None = None,
) -> str:
  run_id = generate_run_id()
  started_at = _utc_now_iso()
  record_live_run(
    action_type=ACTION_TYPE,
    status="success",
    run_id=run_id,
    started_at=started_at,
    user_context=user_context,
    theme_name=str(review.get("theme_name") or "") or None,
    input_summary=f"source={review.get('source_artifact_path')}",
    output_artifact_paths=saved_paths or {},
    source_artifact_paths=[str(review.get("source_artifact_path"))] if review.get("source_artifact_path") else [],
    operation_metadata={
      "signal_count": review.get("total_signal_count"),
      "candidate_information_only": True,
      "no_external_api_call": True,
      "no_email_send": True,
      "no_scheduler_start": True,
    },
    project_root=output_root,
  )
  return run_id


def record_digest_preview_with_web_signals(
  *,
  review: dict[str, Any],
  digest_paths: dict[str, str],
  output_root: Path | str,
  user_context: dict[str, Any] | None = None,
  theme_name: str | None = None,
) -> str:
  run_id = generate_run_id()
  started_at = _utc_now_iso()
  record_live_run(
    action_type=DIGEST_WITH_SIGNALS_ACTION,
    status="success",
    run_id=run_id,
    started_at=started_at,
    user_context=user_context,
    theme_name=theme_name or str(review.get("theme_name") or "") or None,
    input_summary=f"signals={review.get('total_signal_count')}",
    output_artifact_paths=digest_paths,
    source_artifact_paths=[str(review.get("source_artifact_path"))] if review.get("source_artifact_path") else [],
    operation_metadata={
      "signal_count": review.get("total_signal_count"),
      "candidate_information_only": True,
      "no_external_api_call": True,
      "no_email_send": True,
      "no_scheduler_start": True,
    },
    project_root=output_root,
  )
  return run_id


def integrate_review_into_preview(preview: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
  """Append Web Signal section to digest preview bodies."""
  merged = dict(preview)
  section_md = render_web_signal_section_markdown(review)
  section_plain = render_web_signal_section_plain(review)
  merged["web_signal_review"] = review
  merged["web_signal_section_markdown"] = section_md
  merged["web_signal_section_plain"] = section_plain
  merged["uses_web_signals"] = bool(review.get("artifact_exists"))
  merged["source_web_signal_artifact"] = review.get("source_artifact_path")
  merged["markdown_body"] = str(merged.get("markdown_body") or "").rstrip() + "\n\n" + section_md
  merged["plain_text_body"] = str(merged.get("plain_text_body") or "").rstrip() + "\n\n" + section_plain
  return merged
