"""Weekly digest preview generation — no email sending (Phase 24.0)."""

from __future__ import annotations

import html
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.delivery.digest_diff import DigestDiff, WeeklyDigestSnapshot
from tech_cartography.delivery.overview import DELIVERY_CAUTION
from tech_cartography.delivery.report_bundle import REPORT_CAUTION
from tech_cartography.reports.project_export import load_records_csv
from tech_cartography.web_signals.schema import utc_now_iso

import pandas as pd

PREVIEW_ONLY_NOTICE = (
  "Preview only. Email sending is disabled in this phase."
)


@dataclass
class WeeklyDigest:
  digest_id: str
  created_at: str
  subject: str
  markdown_body: str
  html_body: str
  diff_summary: str
  attachments: list[str] = field(default_factory=list)
  caveats: list[str] = field(default_factory=list)
  send_status: str = "preview_only"

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


def _safe_read_csv(path: Path) -> pd.DataFrame:
  if not path.exists():
    return pd.DataFrame()
  try:
    rows = load_records_csv(str(path))
    return pd.DataFrame(rows) if rows else pd.DataFrame()
  except Exception:  # noqa: BLE001
    return pd.DataFrame()


def _format_date_label(created_at: str) -> str:
  try:
    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d")
  except ValueError:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _top_watch_items(root: Path, pub: str, limit: int = 3) -> list[dict[str, str]]:
  path = root / "outputs" / "strategic_watch_briefs" / pub / "top_strategic_watch_items.csv"
  df = _safe_read_csv(path)
  if df.empty:
    path = root / "outputs" / "strategic_watch_briefs" / pub / "strategic_watch_items.csv"
    df = _safe_read_csv(path)
  if df.empty:
    return []
  rows: list[dict[str, str]] = []
  for _, row in df.head(limit).iterrows():
    rows.append(
      {
        "watch_theme": str(row.get("watch_theme", "") or "").strip(),
        "watch_priority": str(row.get("watch_priority", "") or "").strip(),
        "why_it_matters": str(row.get("why_it_matters", "") or "").strip()[:200],
        "next_verification_action": str(row.get("next_verification_action", "") or "").strip()[:200],
      },
    )
  return rows


def build_weekly_digest(
  publication_number: str,
  project_root: Path | str,
  diff: DigestDiff | None = None,
  snapshot: WeeklyDigestSnapshot | None = None,
) -> WeeklyDigest:
  root = Path(project_root)
  pub = str(publication_number).strip()
  created_at = utc_now_iso()
  date_label = _format_date_label(created_at)
  subject = f"[Tech Cartography] Weekly Intelligence Digest - {pub} - {date_label}"

  diff = diff or DigestDiff(is_initial=True)
  top_items = _top_watch_items(root, pub)

  lines = [
    "# Weekly Intelligence Digest",
    "",
    f"- publication_number: {pub}",
    f"- created_at: {created_at}",
    f"- status: {PREVIEW_ONLY_NOTICE}",
    "",
    "## What changed this week",
    "",
  ]

  if diff.is_initial:
    lines.extend(
      [
        "- **Initial digest**: baseline snapshot created.",
        f"- Strategic Watch Items: {len(diff.added_watch_items)}",
        f"- Web Signals: {len(diff.added_web_signals)}",
        f"- Link Candidates: {len(diff.added_links)}",
        f"- Paper Evidence: {len(diff.added_papers)}",
        "",
      ],
    )
  else:
    if diff.unchanged_summary:
      lines.append("- **No change**: summary hash unchanged.")
    if diff.added_watch_items:
      lines.append(f"- **New** Strategic Watch Items: {len(diff.added_watch_items)}")
      for item in diff.added_watch_items[:5]:
        lines.append(f"  - {item}")
    if diff.added_web_signals:
      lines.append(f"- **New** Web Signals: {len(diff.added_web_signals)}")
      for item in diff.added_web_signals[:5]:
        lines.append(f"  - {item}")
    if diff.added_links:
      lines.append(f"- **New** Link Candidates: {len(diff.added_links)}")
      for item in diff.added_links[:5]:
        lines.append(f"  - {item}")
    if diff.added_papers:
      lines.append(f"- **New** Paper Evidence: {len(diff.added_papers)}")
    if diff.changed_statuses:
      lines.append("- **Changed** statuses:")
      for item in diff.changed_statuses[:5]:
        lines.append(f"  - {item}")
    if not any([diff.added_watch_items, diff.added_web_signals, diff.added_links, diff.added_papers, diff.changed_statuses]):
      lines.append("- No major changes detected.")
    lines.append("")

  lines.extend(["## Top 3 Watch Items", ""])
  if top_items:
    for item in top_items:
      lines.extend(
        [
          f"### {item.get('watch_theme') or '(theme n/a)'} [{item.get('watch_priority', 'n/a')}]",
          "",
          f"- why_it_matters: {item.get('why_it_matters') or 'n/a'}",
          f"- next_action: {item.get('next_verification_action') or 'n/a'}",
          "",
        ],
      )
  else:
    lines.append("- (none — generate Strategic Watch Brief first)")
    lines.append("")

  lines.extend(
    [
      "## Evidence Gaps",
      "",
      "- Target patent description/examples may be incomplete.",
      "- Web signal to patent direct linkage is not confirmed.",
      "- Papers are supporting evidence candidates only.",
      "",
      "## Next Verification Actions",
      "",
      "- Open source URLs and verify original documents.",
      "- Confirm claim element / paper / web signal terminology alignment.",
      "- Do not use for FTO, infringement, or validity conclusions.",
      "",
      "## Important Caveats",
      "",
      REPORT_CAUTION,
      "",
      PREVIEW_ONLY_NOTICE,
      "",
      "## Links / Source Artifacts",
      "",
      f"- outputs/strategic_watch_briefs/{pub}/",
      f"- outputs/web_signal_links/{pub}/",
      f"- outputs/evidence_map_synthesis/{pub}/",
      "",
    ],
  )

  markdown_body = "\n".join(lines)
  diff_summary = diff.diff_markdown or "Initial snapshot — no previous digest to compare."

  return WeeklyDigest(
    digest_id=f"digest-{uuid.uuid4().hex[:10]}",
    created_at=created_at,
    subject=subject,
    markdown_body=markdown_body,
    html_body=markdown_to_simple_html(markdown_body),
    diff_summary=diff_summary,
    attachments=[
      f"intelligence_report_{pub}.md",
      f"digest_diff_{pub}.md",
    ],
    caveats=[REPORT_CAUTION, PREVIEW_ONLY_NOTICE, DELIVERY_CAUTION],
    send_status="preview_only",
  )


def markdown_to_simple_html(markdown_text: str) -> str:
  lines = markdown_text.splitlines()
  html_parts: list[str] = [
    "<!DOCTYPE html><html><head><meta charset='utf-8'>",
    "<title>Weekly Intelligence Digest</title>",
    "<style>body{font-family:sans-serif;max-width:800px;margin:2em auto;line-height:1.5;}",
    "h1,h2,h3{color:#1e3a5f;} .notice{background:#fff3cd;padding:12px;border-radius:6px;}</style>",
    "</head><body>",
    f"<p class='notice'><strong>{html.escape(PREVIEW_ONLY_NOTICE)}</strong></p>",
  ]
  for line in lines:
    stripped = line.strip()
    if not stripped:
      continue
    if stripped.startswith("# "):
      html_parts.append(f"<h1>{html.escape(stripped[2:])}</h1>")
    elif stripped.startswith("## "):
      html_parts.append(f"<h2>{html.escape(stripped[3:])}</h2>")
    elif stripped.startswith("### "):
      html_parts.append(f"<h3>{html.escape(stripped[4:])}</h3>")
    elif stripped.startswith("- "):
      text = stripped[2:]
      text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(text))
      html_parts.append(f"<li>{text}</li>")
    else:
      html_parts.append(f"<p>{html.escape(stripped)}</p>")
  html_parts.append("</body></html>")
  return "\n".join(html_parts)
