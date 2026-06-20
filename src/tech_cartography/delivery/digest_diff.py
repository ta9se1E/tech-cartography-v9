"""Digest snapshot and diff for weekly delivery (Phase 24.0)."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from tech_cartography.delivery.overview import DELIVERY_CAUTION
from tech_cartography.reports.project_export import load_records_csv
from tech_cartography.web_signals.schema import utc_now_iso

NOT_AVAILABLE = "not available"


@dataclass
class WeeklyDigestSnapshot:
  snapshot_id: str
  created_at: str
  publication_number: str
  watch_item_ids: list[str] = field(default_factory=list)
  web_signal_ids: list[str] = field(default_factory=list)
  paper_ids: list[str] = field(default_factory=list)
  link_ids: list[str] = field(default_factory=list)
  statuses: dict[str, str] = field(default_factory=dict)
  summary_hash: str = ""
  raw_summary: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class DigestDiff:
  added_watch_items: list[str] = field(default_factory=list)
  removed_watch_items: list[str] = field(default_factory=list)
  changed_watch_items: list[str] = field(default_factory=list)
  added_web_signals: list[str] = field(default_factory=list)
  removed_web_signals: list[str] = field(default_factory=list)
  added_papers: list[str] = field(default_factory=list)
  added_links: list[str] = field(default_factory=list)
  changed_statuses: list[str] = field(default_factory=list)
  unchanged_summary: bool = False
  diff_markdown: str = ""
  is_initial: bool = False

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


def _ids_from_df(df: pd.DataFrame, *columns: str) -> list[str]:
  if df.empty:
    return []
  for col in columns:
    if col in df.columns:
      return sorted(
        str(v).strip()
        for v in df[col].dropna().unique()
        if str(v).strip() and str(v).strip().lower() not in {"nan", "none", ""}
      )
  return []


def _titles_from_df(df: pd.DataFrame, *columns: str) -> list[str]:
  if df.empty:
    return []
  for col in columns:
    if col in df.columns:
      return sorted(
        str(v).strip()[:120]
        for v in df[col].dropna().unique()
        if str(v).strip() and str(v).strip().lower() not in {"nan", "none", ""}
      )
  return []


def _artifact_paths(root: Path, pub: str) -> dict[str, Path]:
  return {
    "watch_items": root / "outputs" / "strategic_watch_briefs" / pub / "strategic_watch_items.csv",
    "top_watch": root / "outputs" / "strategic_watch_briefs" / pub / "top_strategic_watch_items.csv",
    "web_signals": root / "outputs" / "web_signals" / "tavily_pan_carbon_fiber" / "review_pack" / "high_priority_web_signals.csv",
    "web_links": root / "outputs" / "web_signal_links" / pub / "high_priority_web_signal_links.csv",
    "papers": root / "outputs" / "openalex_limited_execution" / "selected_evidence_papers.csv",
    "reproducibility": root / "outputs" / "reproducibility_smoke" / "reproducibility_summary.csv",
  }


def build_digest_snapshot(
  project_root: Path | str,
  publication_number: str,
) -> WeeklyDigestSnapshot:
  root = Path(project_root)
  pub = str(publication_number).strip()
  paths = _artifact_paths(root, pub)

  watch_df = _safe_read_csv(paths["watch_items"])
  if watch_df.empty:
    watch_df = _safe_read_csv(paths["top_watch"])
  web_df = _safe_read_csv(paths["web_signals"])
  links_df = _safe_read_csv(paths["web_links"])
  papers_df = _safe_read_csv(paths["papers"])
  repro_df = _safe_read_csv(paths["reproducibility"])

  watch_ids = _ids_from_df(watch_df, "watch_id")
  web_ids = _ids_from_df(web_df, "signal_id", "web_signal_id")
  paper_ids = _ids_from_df(papers_df, "paper_id", "openalex_id", "doi")
  if not paper_ids:
    paper_ids = _titles_from_df(papers_df, "title", "paper_title")
  link_ids = _ids_from_df(links_df, "link_id")

  statuses: dict[str, str] = {}
  if not repro_df.empty and "publication_number" in repro_df.columns:
    for _, row in repro_df.iterrows():
      pub_key = str(row.get("publication_number", "")).strip()
      status = str(row.get("status") or row.get("synthesis_status") or "").strip()
      if pub_key:
        statuses[pub_key] = status

  summary_parts = watch_ids + web_ids + paper_ids + link_ids + list(statuses.values())
  summary_hash = hashlib.sha256("|".join(summary_parts).encode()).hexdigest()[:16]
  raw_summary = (
    f"watch={len(watch_ids)} web={len(web_ids)} papers={len(paper_ids)} "
    f"links={len(link_ids)} statuses={len(statuses)}"
  )

  return WeeklyDigestSnapshot(
    snapshot_id=f"snap-{uuid.uuid4().hex[:10]}",
    created_at=utc_now_iso(),
    publication_number=pub,
    watch_item_ids=watch_ids,
    web_signal_ids=web_ids,
    paper_ids=paper_ids,
    link_ids=link_ids,
    statuses=statuses,
    summary_hash=summary_hash,
    raw_summary=raw_summary,
  )


def save_digest_snapshot(snapshot: WeeklyDigestSnapshot, output_dir: Path | str) -> Path:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  snapshots_dir = out / "snapshots"
  snapshots_dir.mkdir(parents=True, exist_ok=True)

  timestamp = snapshot.created_at.replace(":", "").replace("+", "p")[:15]
  named = snapshots_dir / f"{timestamp}_{snapshot.publication_number}.json"
  named.write_text(json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

  latest = out / "latest_snapshot.json"
  latest.write_text(json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
  return named


def load_latest_snapshot(snapshot_dir: Path | str) -> WeeklyDigestSnapshot | None:
  latest = Path(snapshot_dir) / "latest_snapshot.json"
  if not latest.exists():
    snapshots = sorted((Path(snapshot_dir) / "snapshots").glob("*.json"))
    if not snapshots:
      return None
    latest = snapshots[-1]
  try:
    data = json.loads(latest.read_text(encoding="utf-8"))
    return WeeklyDigestSnapshot(**data)
  except (OSError, json.JSONDecodeError, TypeError):
    return None


def load_snapshot_file(path: Path | str) -> WeeklyDigestSnapshot | None:
  p = Path(path)
  if not p.exists():
    return None
  try:
    data = json.loads(p.read_text(encoding="utf-8"))
    return WeeklyDigestSnapshot(**data)
  except (OSError, json.JSONDecodeError, TypeError):
    return None


def compare_digest_snapshots(
  previous: WeeklyDigestSnapshot | None,
  current: WeeklyDigestSnapshot,
) -> DigestDiff:
  if previous is None:
    diff = DigestDiff(
      added_watch_items=list(current.watch_item_ids),
      added_web_signals=list(current.web_signal_ids),
      added_papers=list(current.paper_ids),
      added_links=list(current.link_ids),
      is_initial=True,
    )
    diff.diff_markdown = render_digest_diff_markdown(diff, current.publication_number, initial=True)
    return diff

  prev_watch = set(previous.watch_item_ids)
  curr_watch = set(current.watch_item_ids)
  prev_web = set(previous.web_signal_ids)
  curr_web = set(current.web_signal_ids)
  prev_papers = set(previous.paper_ids)
  curr_papers = set(current.paper_ids)
  prev_links = set(previous.link_ids)
  curr_links = set(current.link_ids)

  changed_statuses: list[str] = []
  for key in set(previous.statuses) | set(current.statuses):
    old = previous.statuses.get(key, "")
    new = current.statuses.get(key, "")
    if old != new:
      changed_statuses.append(f"{key}: {old or '(none)'} -> {new or '(none)'}")

  diff = DigestDiff(
    added_watch_items=sorted(curr_watch - prev_watch),
    removed_watch_items=sorted(prev_watch - curr_watch),
    changed_watch_items=[],
    added_web_signals=sorted(curr_web - prev_web),
    removed_web_signals=sorted(prev_web - curr_web),
    added_papers=sorted(curr_papers - prev_papers),
    added_links=sorted(curr_links - prev_links),
    changed_statuses=changed_statuses,
    unchanged_summary=previous.summary_hash == current.summary_hash and not changed_statuses,
  )
  diff.diff_markdown = render_digest_diff_markdown(diff, current.publication_number)
  return diff


def render_digest_diff_short_summary(diff: DigestDiff) -> str:
  """One-line Japanese summary for digest body and email subject lines."""
  if diff.is_initial:
    return (
      "初回ベースラインを作成しました。"
      f"監視候補 {len(diff.added_watch_items)} 件 / "
      f"Webシグナル {len(diff.added_web_signals)} 件 / "
      f"リンク {len(diff.added_links)} 件 / "
      f"論文 {len(diff.added_papers)} 件"
    )

  has_changes = any(
    [
      diff.added_watch_items,
      diff.removed_watch_items,
      diff.added_web_signals,
      diff.removed_web_signals,
      diff.added_links,
      diff.added_papers,
      diff.changed_statuses,
    ],
  )
  if diff.unchanged_summary and not has_changes:
    return "今週の主要な変更はありません（No Major Changes）。"

  parts: list[str] = []
  if diff.added_watch_items:
    parts.append(f"新規Watch Item {len(diff.added_watch_items)} 件")
  if diff.removed_watch_items:
    parts.append(f"削除Watch Item {len(diff.removed_watch_items)} 件")
  if diff.added_web_signals:
    parts.append(f"新規Web Signal {len(diff.added_web_signals)} 件")
  if diff.added_links:
    parts.append(f"新規Link Candidate {len(diff.added_links)} 件")
  if diff.added_papers:
    parts.append(f"新規Paper Evidence {len(diff.added_papers)} 件")
  if diff.changed_statuses:
    parts.append(f"状態変化 {len(diff.changed_statuses)} 件")

  return " / ".join(parts) if parts else "今週の主要な変更はありません（No Major Changes）。"


def render_digest_diff_markdown(
  diff: DigestDiff,
  publication_number: str,
  *,
  initial: bool = False,
) -> str:
  lines = [
    f"# Digest Diff: {publication_number}",
    "",
    f"**要約**: {render_digest_diff_short_summary(diff)}",
    "",
  ]
  if initial or diff.is_initial:
    lines.extend(
      [
        "## Initial Snapshot / 初回ベースライン",
        "",
        "初回の Digest Snapshot です。現在の項目をすべてベースラインとして記録しました。",
        "This is the first digest snapshot. All current items are treated as baseline.",
        "",
        f"- Strategic Watch Items（監視候補）: {len(diff.added_watch_items)}",
        f"- Web Signals（Webシグナル）: {len(diff.added_web_signals)}",
        f"- Paper Evidence（論文候補）: {len(diff.added_papers)}",
        f"- Link Candidates（リンク候補）: {len(diff.added_links)}",
        "",
      ],
    )
    return "\n".join(lines)

  if diff.unchanged_summary:
    lines.extend(
      [
        "## No Major Changes / 主要な変更なし",
        "",
        "前回 Snapshot からサマリーハッシュに変更はありません。",
        "Summary hash unchanged since previous snapshot.",
        "",
      ],
    )

  def _section(title_en: str, title_ja: str, items: list[str], label: str) -> None:
    lines.extend([f"## {title_en} / {title_ja}", ""])
    if items:
      for item in items[:20]:
        lines.append(f"- **{label}**: {item}")
    else:
      lines.append("- （なし / none）")
    lines.append("")

  _section("New Strategic Watch Items", "新規監視候補", diff.added_watch_items, "追加")
  if diff.removed_watch_items:
    lines.extend(["## Removed Strategic Watch Items / 削除された監視候補", ""])
    for item in diff.removed_watch_items[:10]:
      lines.append(f"- **削除**: {item}")
    lines.append("")

  _section("New Web Signals", "新規Webシグナル", diff.added_web_signals, "追加")
  if diff.removed_web_signals:
    lines.extend(["## Removed Web Signals / 削除されたWebシグナル", ""])
    for item in diff.removed_web_signals[:10]:
      lines.append(f"- **削除**: {item}")
    lines.append("")

  _section("New Patent × Paper × Web Links", "新規リンク候補", diff.added_links, "追加")
  _section("New Paper Evidence Candidates", "新規論文候補", diff.added_papers, "追加")

  if diff.changed_statuses:
    lines.extend(["## Status Changes / ステータス変化", ""])
    for item in diff.changed_statuses:
      lines.append(f"- **変更**: {item}")
    lines.append("")

  lines.extend(
    [
      "## Still Needs Manual Review",
      "",
      "All web signals, link candidates, and strategic watch items require human verification.",
      "",
      DELIVERY_CAUTION,
      "",
    ],
  )
  return "\n".join(lines)
