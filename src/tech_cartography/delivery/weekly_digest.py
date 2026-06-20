"""Weekly digest preview generation — email-ready Japanese body (Phase 24.1)."""

from __future__ import annotations

import html
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.delivery.digest_diff import (
  DigestDiff,
  WeeklyDigestSnapshot,
  render_digest_diff_short_summary,
)
from tech_cartography.delivery.overview import DELIVERY_CAUTION
from tech_cartography.delivery.report_bundle import REPORT_CAUTION
from tech_cartography.reports.project_export import load_records_csv
from tech_cartography.web_signals.schema import utc_now_iso

import pandas as pd

PREVIEW_ONLY_NOTICE = (
  "Preview only. Email sending is disabled in this phase."
)
PREVIEW_ONLY_NOTICE_JA = (
  "プレビューのみ。この段階ではメール送信は行いません。"
)

DIGEST_CAUTIONS_JA = [
  "本レポートは FTO・侵害・有効性の判断ではありません。",
  "Web signals are signal candidates, not final conclusions.",
  "Papers are supporting evidence candidates, not proof of patent claims.",
  "Strategic Watch items are monitoring candidates, not final conclusions.",
  "Synthetic demo signals must be clearly labeled before use.",
  "金額の断定表示は行いません。",
  "high confidence の自動付与は行いません。",
]

_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
_AGENCY_PATTERNS = (
  ("NEDO", ("nedo", "新エネルギー")),
  ("JST", ("jst", "科学技術振興機構")),
  ("METI", ("meti", "経済産業省")),
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


def truncate_at_sentence_boundary(text: str, max_chars: int = 220) -> str:
  """Truncate text at a sentence or word boundary; avoid mid-word cuts."""
  raw = str(text or "").strip()
  if not raw or len(raw) <= max_chars:
    return raw

  chunk = raw[:max_chars]
  best_cut = -1
  for sep in ("。", ". ", ".\n", "! ", "? ", "、", "; "):
    idx = chunk.rfind(sep)
    if idx >= int(max_chars * 0.35):
      best_cut = max(best_cut, idx + len(sep.rstrip()))

  if best_cut > 0:
    return chunk[:best_cut].strip() + "（要確認）"

  for sep in (" ", "　"):
    idx = chunk.rfind(sep)
    if idx >= int(max_chars * 0.5):
      return chunk[:idx].strip() + "（要確認）"

  return chunk.strip() + "（要確認）"


def _norm_key(value: object) -> str:
  return str(value or "").strip().lower()


def _watch_item_sort_key(item: dict[str, str]) -> tuple[int, float]:
  priority = _PRIORITY_RANK.get(str(item.get("watch_priority", "")).strip().lower(), 3)
  try:
    score = -float(item.get("link_score") or 0)
  except (TypeError, ValueError):
    score = 0.0
  return (priority, score)


def _item_conflicts(
  item: dict[str, str],
  seen_themes: set[str],
  seen_web: set[str],
  seen_paper: set[str],
  seen_types: set[str],
  *,
  check_type: bool = True,
) -> bool:
  theme = _norm_key(item.get("watch_theme"))
  web = _norm_key(item.get("related_web_signal_title"))
  paper = _norm_key(item.get("related_paper_title"))
  watch_type = _norm_key(item.get("watch_type"))
  if theme and theme in seen_themes:
    return True
  if web and web in seen_web:
    return True
  if paper and paper in seen_paper:
    return True
  if check_type and watch_type and watch_type in seen_types:
    return True
  return False


def _track_item(
  item: dict[str, str],
  seen_themes: set[str],
  seen_web: set[str],
  seen_paper: set[str],
  seen_types: set[str],
) -> None:
  theme = _norm_key(item.get("watch_theme"))
  web = _norm_key(item.get("related_web_signal_title"))
  paper = _norm_key(item.get("related_paper_title"))
  watch_type = _norm_key(item.get("watch_type"))
  if theme:
    seen_themes.add(theme)
  if web:
    seen_web.add(web)
  if paper:
    seen_paper.add(paper)
  if watch_type:
    seen_types.add(watch_type)


def select_diverse_top_watch_items(items: list[dict[str, str]], top_n: int = 3) -> list[dict[str, str]]:
  """Pick top_n watch items while avoiding duplicate themes, signals, papers, and types."""
  if not items:
    return []
  if top_n <= 0:
    return []

  sorted_items = sorted(items, key=_watch_item_sort_key)
  selected: list[dict[str, str]] = []
  seen_themes: set[str] = set()
  seen_web: set[str] = set()
  seen_paper: set[str] = set()
  seen_types: set[str] = set()

  def try_pass(*, check_type: bool, check_theme: bool, check_web: bool, check_paper: bool) -> None:
    for item in sorted_items:
      if len(selected) >= top_n or item in selected:
        continue
      theme = _norm_key(item.get("watch_theme"))
      web = _norm_key(item.get("related_web_signal_title"))
      paper = _norm_key(item.get("related_paper_title"))
      watch_type = _norm_key(item.get("watch_type"))
      if check_theme and theme and theme in seen_themes:
        continue
      if check_web and web and web in seen_web:
        continue
      if check_paper and paper and paper in seen_paper:
        continue
      if check_type and watch_type and watch_type in seen_types:
        continue
      selected.append(item)
      _track_item(item, seen_themes, seen_web, seen_paper, seen_types)

  try_pass(check_type=True, check_theme=True, check_web=True, check_paper=True)
  try_pass(check_type=False, check_theme=True, check_web=True, check_paper=True)
  try_pass(check_type=False, check_theme=True, check_web=True, check_paper=False)
  try_pass(check_type=False, check_theme=False, check_web=True, check_paper=False)

  for item in sorted_items:
    if len(selected) >= top_n:
      break
    if item in selected:
      continue
    web = _norm_key(item.get("related_web_signal_title"))
    if web and web in seen_web:
      continue
    selected.append(item)
    _track_item(item, seen_themes, seen_web, seen_paper, seen_types)

  return selected[:top_n]


def _extract_agency_label(web_title: str, domain: str) -> str:
  combined = f"{web_title} {domain}".lower()
  for label, tokens in _AGENCY_PATTERNS:
    if any(token in combined for token in tokens):
      return label
  return ""


def build_digest_item_title(item: dict[str, str]) -> str:
  """Build a distinctive digest heading using source title when themes repeat."""
  web_title = str(item.get("related_web_signal_title") or "").strip()
  domain = str(item.get("related_web_signal_domain") or "").strip()
  theme = str(item.get("watch_theme") or "").strip()
  watch_type = str(item.get("watch_type") or "").strip()
  paper = str(item.get("related_paper_title") or "").strip()

  agency = _extract_agency_label(web_title, domain)
  if web_title:
    short = truncate_at_sentence_boundary(web_title, 80)
    if agency:
      return f"{agency}: {short}"
    return short
  if paper:
    return truncate_at_sentence_boundary(paper, 80)
  if theme and watch_type:
    return f"{theme} ({watch_type})"
  return theme or "(テーマ不明)"


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


def _row_to_watch_item(row: pd.Series) -> dict[str, str]:
  return {
    "watch_theme": str(row.get("watch_theme", "") or "").strip(),
    "watch_type": str(row.get("watch_type", "") or "").strip(),
    "watch_priority": str(row.get("watch_priority", "") or "").strip(),
    "why_it_matters": truncate_at_sentence_boundary(str(row.get("why_it_matters", "") or "")),
    "next_verification_action": truncate_at_sentence_boundary(
      str(row.get("next_verification_action", "") or ""),
      max_chars=180,
    ),
    "related_web_signal_title": str(row.get("related_web_signal_title", "") or "").strip(),
    "related_web_signal_domain": str(row.get("related_web_signal_domain", "") or "").strip(),
    "related_paper_title": str(row.get("related_paper_title", "") or "").strip(),
    "evidence_basis": truncate_at_sentence_boundary(str(row.get("evidence_basis", "") or ""), max_chars=180),
    "link_score": str(row.get("link_score", "") or "").strip(),
  }


def _load_watch_items(root: Path, pub: str) -> list[dict[str, str]]:
  path = root / "outputs" / "strategic_watch_briefs" / pub / "top_strategic_watch_items.csv"
  df = _safe_read_csv(path)
  if df.empty:
    path = root / "outputs" / "strategic_watch_briefs" / pub / "strategic_watch_items.csv"
    df = _safe_read_csv(path)
  if df.empty:
    return []
  return [_row_to_watch_item(row) for _, row in df.iterrows()]


def _priority_label_ja(priority: str) -> str:
  mapping = {"high": "高", "medium": "中", "low": "低"}
  return mapping.get(str(priority or "").strip().lower(), priority or "不明")


def _render_diff_section(diff: DigestDiff) -> list[str]:
  lines = ["## 今週の差分", ""]
  short = render_digest_diff_short_summary(diff)
  lines.append(f"- {short}")

  if diff.is_initial:
    lines.extend(
      [
        f"- 初回ベースライン: Strategic Watch {len(diff.added_watch_items)} 件",
        f"- Web Signals: {len(diff.added_web_signals)} 件",
        f"- Link Candidates: {len(diff.added_links)} 件",
        f"- Paper Evidence: {len(diff.added_papers)} 件",
        "",
        "_English supplement: Initial digest baseline created._",
        "",
      ],
    )
    return lines

  if diff.unchanged_summary:
    lines.append("- サマリーハッシュに変更なし（No Major Changes）")

  if diff.added_watch_items:
    lines.append(f"- **追加** Strategic Watch Items: {len(diff.added_watch_items)} 件")
    for item in diff.added_watch_items[:5]:
      lines.append(f"  - {item}")
  if diff.removed_watch_items:
    lines.append(f"- **削除** Strategic Watch Items: {len(diff.removed_watch_items)} 件")
  if diff.added_web_signals:
    lines.append(f"- **追加** Web Signals: {len(diff.added_web_signals)} 件")
    for item in diff.added_web_signals[:5]:
      lines.append(f"  - {item}")
  if diff.added_links:
    lines.append(f"- **追加** Link Candidates: {len(diff.added_links)} 件")
    for item in diff.added_links[:5]:
      lines.append(f"  - {item}")
  if diff.added_papers:
    lines.append(f"- **追加** Paper Evidence: {len(diff.added_papers)} 件")
  if diff.changed_statuses:
    lines.append("- **変更** ステータス:")
    for item in diff.changed_statuses[:5]:
      lines.append(f"  - {item}")

  if not any(
    [
      diff.added_watch_items,
      diff.removed_watch_items,
      diff.added_web_signals,
      diff.added_links,
      diff.added_papers,
      diff.changed_statuses,
    ],
  ) and not diff.unchanged_summary:
    lines.append("- 今週の主要な変更はありません（No Major Changes）")

  lines.extend(["", "_English supplement: What changed this week._", ""])
  return lines


def _render_top_watch_section(top_items: list[dict[str, str]]) -> list[str]:
  lines = ["## 今週の重点監視候補 Top 3", ""]
  if not top_items:
    lines.extend(
      [
        "- （なし — Strategic Watch Brief を先に生成してください）",
        "",
        "_English supplement: Top 3 Watch Items — none available._",
        "",
      ],
    )
    return lines

  for index, item in enumerate(top_items, start=1):
    title = build_digest_item_title(item)
    priority = _priority_label_ja(item.get("watch_priority", ""))
    lines.extend(
      [
        f"### {index}. {title} [優先度: {priority}]",
        "",
        f"- **テーマ**: {item.get('watch_theme') or '—'}",
        f"- **種別 (watch_type)**: {item.get('watch_type') or '—'}",
        f"- **なぜ見るべきか**: {item.get('why_it_matters') or '—'}",
        f"- **根拠**: {item.get('evidence_basis') or '—'}",
        f"- **次に確認すること**: {item.get('next_verification_action') or '—'}",
        "- **注意**: 最終結論ではありません。手動確認が必要です。",
        "",
      ],
    )
  lines.extend(["_English supplement: Top 3 Watch Items._", ""])
  return lines


def _render_signals_section(root: Path, pub: str) -> list[str]:
  lines = ["## 新規・更新シグナル", ""]

  web_path = (
    root / "outputs" / "web_signals" / "tavily_pan_carbon_fiber" / "review_pack"
    / "high_priority_web_signals.csv"
  )
  web_df = _safe_read_csv(web_path)
  lines.append("### Web Signal")
  if web_df.empty:
    lines.append("- （なし）")
  else:
    title_col = "source_title" if "source_title" in web_df.columns else "title"
    for _, row in web_df.head(5).iterrows():
      title = truncate_at_sentence_boundary(str(row.get(title_col, "") or ""), max_chars=100)
      lines.append(f"- {title or '(title n/a)'}")
  lines.append("")

  paper_path = root / "outputs" / "openalex_limited_execution" / "selected_evidence_papers.csv"
  paper_df = _safe_read_csv(paper_path)
  lines.append("### Paper Evidence")
  if paper_df.empty:
    lines.append("- （なし）")
  else:
    for _, row in paper_df.head(5).iterrows():
      title = truncate_at_sentence_boundary(str(row.get("title", "") or ""), max_chars=100)
      lines.append(f"- {title or '(title n/a)'}")
  lines.append("")

  link_path = root / "outputs" / "web_signal_links" / pub / "high_priority_web_signal_links.csv"
  link_df = _safe_read_csv(link_path)
  lines.append("### Patent × Paper × Web Link")
  if link_df.empty:
    lines.append("- （なし）")
  else:
    for _, row in link_df.head(5).iterrows():
      title = truncate_at_sentence_boundary(
        str(row.get("web_signal_title", "") or row.get("link_summary", "") or ""),
        max_chars=100,
      )
      lines.append(f"- {title or '(link n/a)'}")
  lines.append("")
  return lines


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
  all_items = _load_watch_items(root, pub)
  top_items = select_diverse_top_watch_items(all_items, top_n=3)

  lines = [
    "# Tech Cartography Weekly Digest",
    "",
    f"- 対象特許: {pub}",
    f"- 作成日時: {created_at}",
    f"- ステータス: {PREVIEW_ONLY_NOTICE_JA}",
    f"- _Status (EN): {PREVIEW_ONLY_NOTICE}_",
    "",
  ]
  lines.extend(_render_diff_section(diff))
  lines.extend(_render_top_watch_section(top_items))
  lines.extend(_render_signals_section(root, pub))
  lines.extend(
    [
      "## Evidence Gaps",
      "",
      "- 対象特許の description / examples が不完全な場合があります。",
      "- Web signal と特許の直接リンクは未確認です。",
      "- Papers are supporting evidence candidates, not proof of patent claims.",
      "",
      "## Next Verification Actions",
      "",
      "- 元URLを開き、一次情報を確認してください。",
      "- claim element / paper / web signal の用語整合を確認してください。",
      "- FTO・侵害・有効性の結論には使用しないでください。",
      "",
      "## Important Caveats",
      "",
    ],
  )
  for caveat in DIGEST_CAUTIONS_JA:
    lines.append(f"- {caveat}")
  lines.extend(
    [
      "",
      REPORT_CAUTION,
      "",
      DELIVERY_CAUTION,
      "",
      PREVIEW_ONLY_NOTICE_JA,
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
  diff_summary = render_digest_diff_short_summary(diff)

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
    caveats=[*DIGEST_CAUTIONS_JA, REPORT_CAUTION, PREVIEW_ONLY_NOTICE, DELIVERY_CAUTION],
    send_status="preview_only",
  )


def markdown_to_simple_html(markdown_text: str) -> str:
  lines = markdown_text.splitlines()
  html_parts: list[str] = [
    "<!DOCTYPE html><html><head><meta charset='utf-8'>",
    "<title>Tech Cartography Weekly Digest</title>",
    "<style>body{font-family:sans-serif;max-width:800px;margin:2em auto;line-height:1.5;}",
    "h1,h2,h3{color:#1e3a5f;} .notice{background:#fff3cd;padding:12px;border-radius:6px;}</style>",
    "</head><body>",
    f"<p class='notice'><strong>{html.escape(PREVIEW_ONLY_NOTICE_JA)}</strong></p>",
    f"<p class='notice'><em>{html.escape(PREVIEW_ONLY_NOTICE)}</em></p>",
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
    elif stripped.startswith("_") and stripped.endswith("_"):
      html_parts.append(f"<p><em>{html.escape(stripped.strip('_'))}</em></p>")
    else:
      html_parts.append(f"<p>{html.escape(stripped)}</p>")
  html_parts.append("</body></html>")
  return "\n".join(html_parts)
