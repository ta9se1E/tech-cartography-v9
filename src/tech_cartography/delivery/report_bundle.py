"""Build unified Intelligence Report from existing outputs (Phase 24.0)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from tech_cartography.delivery.overview import DELIVERY_CAUTION
from tech_cartography.reports.project_export import load_records_csv
from tech_cartography.web_signals.schema import utc_now_iso

NOT_AVAILABLE = "Not available in this run.\nNext action: generate the corresponding artifact first."

REPORT_CAUTION = (
  "This report is not a final conclusion.\n"
  "Web signals are signal candidates, not final conclusions.\n"
  "Papers are supporting evidence candidates, not proof of patent claims.\n"
  "This is not FTO, infringement, or validity analysis.\n"
  "IR / disclosure signals require document-level verification.\n"
  "Money / national_project signals require source verification.\n"
  "Synthetic demo signal must be clearly labeled."
)


@dataclass
class ReportSection:
  section_id: str
  heading: str
  summary: str
  markdown_body: str
  artifact_paths: list[str] = field(default_factory=list)
  missing_artifacts: list[str] = field(default_factory=list)
  caveat: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class ReportBundle:
  publication_number: str
  created_at: str
  title: str
  sections: list[ReportSection]
  source_artifacts: dict[str, str]
  caveats: list[str]
  markdown: str

  def to_dict(self) -> dict[str, Any]:
    return {
      "publication_number": self.publication_number,
      "created_at": self.created_at,
      "title": self.title,
      "sections": [s.to_dict() for s in self.sections],
      "source_artifacts": dict(self.source_artifacts),
      "caveats": list(self.caveats),
      "markdown": self.markdown,
    }


def _safe_read_text(path: Path) -> str | None:
  if not path.exists():
    return None
  try:
    return path.read_text(encoding="utf-8")
  except OSError:
    return None


def _safe_read_csv(path: Path) -> pd.DataFrame:
  if not path.exists():
    return pd.DataFrame()
  try:
    rows = load_records_csv(str(path))
    return pd.DataFrame(rows) if rows else pd.DataFrame()
  except Exception:  # noqa: BLE001
    return pd.DataFrame()


def _safe_read_json(path: Path) -> dict[str, Any]:
  if not path.exists():
    return {}
  try:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    return parsed if isinstance(parsed, dict) else {}
  except (OSError, json.JSONDecodeError):
    return {}


def _artifact_section(
  section_id: str,
  heading: str,
  path: Path,
  *,
  summary: str = "",
) -> ReportSection:
  body = _safe_read_text(path)
  missing: list[str] = []
  if body is None:
    missing.append(str(path))
    body = NOT_AVAILABLE
  return ReportSection(
    section_id=section_id,
    heading=heading,
    summary=summary or (f"Loaded from {path.name}" if not missing else "Artifact missing"),
    markdown_body=body,
    artifact_paths=[str(path)] if not missing else [],
    missing_artifacts=missing,
    caveat=DELIVERY_CAUTION,
  )


def _papers_summary(path: Path) -> ReportSection:
  df = _safe_read_csv(path)
  if df.empty:
    return ReportSection(
      section_id="paper_evidence",
      heading="Paper Evidence Candidates",
      summary="No paper evidence CSV found",
      markdown_body=NOT_AVAILABLE,
      missing_artifacts=[str(path)],
      caveat="Papers are supporting evidence candidates, not proof of patent claims.",
    )
  lines = [f"Selected evidence papers: {len(df)} rows", ""]
  title_col = "title" if "title" in df.columns else df.columns[0] if len(df.columns) else "title"
  for _, row in df.head(10).iterrows():
    title = str(row.get(title_col, "") or "").strip()
    if title:
      lines.append(f"- {title[:120]}")
  return ReportSection(
    section_id="paper_evidence",
    heading="Paper Evidence Candidates",
    summary=f"{len(df)} selected evidence papers",
    markdown_body="\n".join(lines),
    artifact_paths=[str(path)],
    caveat="Papers are supporting evidence candidates, not proof of patent claims.",
  )


def _default_artifact_paths(root: Path, pub: str) -> dict[str, Path]:
  return {
    "evidence_map_synthesis": root / "outputs" / "evidence_map_synthesis" / pub / "evidence_map_synthesis.md",
    "evidence_map_json": root / "outputs" / "evidence_map_synthesis" / pub / "evidence_map_synthesis.json",
    "reproducibility_summary": root / "outputs" / "reproducibility_smoke" / "reproducibility_summary.md",
    "web_signal_review": root / "outputs" / "web_signals" / "tavily_pan_carbon_fiber" / "review_pack" / "web_signal_review_summary.md",
    "web_signal_links_summary": root / "outputs" / "web_signal_links" / pub / "patent_paper_web_signal_summary.md",
    "web_signal_links_actions": root / "outputs" / "web_signal_links" / pub / "next_verification_actions.md",
    "strategic_watch_brief": root / "outputs" / "strategic_watch_briefs" / pub / "strategic_watch_brief.md",
    "strategic_watch_actions": root / "outputs" / "strategic_watch_briefs" / pub / "strategic_watch_next_actions.md",
    "selected_papers": root / "outputs" / "openalex_limited_execution" / "selected_evidence_papers.csv",
  }


def build_report_bundle(
  publication_number: str,
  project_root: Path | str = ".",
) -> ReportBundle:
  root = Path(project_root)
  pub = str(publication_number).strip()
  paths = _default_artifact_paths(root, pub)
  synthesis_json = _safe_read_json(paths["evidence_map_json"])
  patent_title = str(synthesis_json.get("title") or synthesis_json.get("patent_title") or pub)

  sections = [
    ReportSection(
      section_id="executive_summary",
      heading="Executive Summary",
      summary=f"Intelligence report for {pub}",
      markdown_body=(
        f"This Tech Cartography Intelligence Report consolidates Evidence Map, "
        f"Reproducibility, Web Signals, Link Candidates, and Strategic Watch Brief "
        f"for **{patent_title}** ({pub}).\n\n"
        "Use this report for team review and weekly monitoring. "
        "It is not a final legal or strategic conclusion."
      ),
      caveat=REPORT_CAUTION,
    ),
    ReportSection(
      section_id="how_to_read",
      heading="How to Read This Report",
      summary="Reading guide",
      markdown_body=(
        "1. Start with Evidence Map Summary for claim/paper alignment.\n"
        "2. Check Reproducibility Status for pipeline health.\n"
        "3. Review Web Signal and Link Candidates as signal candidates only.\n"
        "4. Use Strategic Watch Brief for monitoring priorities.\n"
        "5. Follow Next Verification Actions before any strategic use."
      ),
      caveat=DELIVERY_CAUTION,
    ),
    ReportSection(
      section_id="target_patent",
      heading="Target Patent",
      summary=patent_title,
      markdown_body=f"- publication_number: {pub}\n- title: {patent_title}",
      artifact_paths=[str(paths["evidence_map_json"])] if paths["evidence_map_json"].exists() else [],
      missing_artifacts=[] if paths["evidence_map_json"].exists() else [str(paths["evidence_map_json"])],
    ),
    _artifact_section("evidence_map", "Evidence Map Summary", paths["evidence_map_synthesis"]),
    _artifact_section("reproducibility", "Reproducibility Status", paths["reproducibility_summary"]),
    _papers_summary(paths["selected_papers"]),
    _artifact_section("web_signal_review", "Web Signal Review", paths["web_signal_review"]),
    _artifact_section(
      "web_signal_links",
      "Patent × Paper × Web Signal Link Candidates",
      paths["web_signal_links_summary"],
    ),
    _artifact_section("strategic_watch", "Strategic Watch Brief", paths["strategic_watch_brief"]),
    ReportSection(
      section_id="evidence_gaps",
      heading="Evidence Gaps",
      summary="Gaps requiring manual follow-up",
      markdown_body=_build_evidence_gaps_body(synthesis_json, paths),
      caveat="Claims-only route limits confidence to medium at most.",
    ),
    ReportSection(
      section_id="next_actions",
      heading="Next Verification Actions",
      summary="Combined next actions",
      markdown_body=_build_next_actions_body(paths),
      caveat=DELIVERY_CAUTION,
    ),
    ReportSection(
      section_id="caveats",
      heading="Important Caveats",
      summary="Mandatory disclaimers",
      markdown_body=REPORT_CAUTION,
    ),
    ReportSection(
      section_id="source_artifacts",
      heading="Source Artifacts",
      summary="Input file index",
      markdown_body=_build_source_index(paths),
    ),
  ]

  markdown = _render_bundle_markdown(pub, patent_title, sections)
  source_artifacts = {key: str(path) for key, path in paths.items()}

  return ReportBundle(
    publication_number=pub,
    created_at=utc_now_iso(),
    title=f"Tech Cartography Intelligence Report: {pub}",
    sections=sections,
    source_artifacts=source_artifacts,
    caveats=[REPORT_CAUTION],
    markdown=markdown,
  )


def _build_evidence_gaps_body(synthesis: dict[str, Any], paths: dict[str, Path]) -> str:
  gaps = synthesis.get("evidence_gaps_japanese") or synthesis.get("evidence_gaps") or []
  if isinstance(gaps, str):
    gaps = [gaps]
  lines: list[str] = []
  if gaps:
    for gap in gaps[:8]:
      lines.append(f"- {gap}")
  else:
    lines.append("- Target patent description/examples may be incomplete.")
    lines.append("- Web signal to patent direct linkage is not confirmed.")
    lines.append("- Papers are supporting evidence candidates only.")
  if not paths["evidence_map_synthesis"].exists():
    lines.append(f"\n{NOT_AVAILABLE}")
  return "\n".join(lines)


def _build_next_actions_body(paths: dict[str, Path]) -> str:
  parts: list[str] = []
  for key, label in (
    ("web_signal_links_actions", "Web Signal Links"),
    ("strategic_watch_actions", "Strategic Watch"),
  ):
    text = _safe_read_text(paths[key])
    if text:
      parts.append(f"### {label}\n\n{text[:2000]}")
  if not parts:
    return NOT_AVAILABLE
  return "\n\n".join(parts)


def _build_source_index(paths: dict[str, Path]) -> str:
  lines = ["| Artifact | Status |", "|----------|--------|"]
  for key, path in paths.items():
    status = "available" if path.exists() else "missing"
    lines.append(f"| {key} | {status} |")
    lines.append(f"| path: `{path}` | |")
  return "\n".join(lines)


def _render_bundle_markdown(pub: str, title: str, sections: list[ReportSection]) -> str:
  lines = [
    f"# Tech Cartography Intelligence Report",
    "",
    f"- publication_number: {pub}",
    f"- patent_title: {title}",
    "",
  ]
  for idx, section in enumerate(sections, start=1):
    if section.section_id in {"executive_summary", "how_to_read", "caveats"}:
      num = {"executive_summary": 1, "how_to_read": 2}.get(section.section_id, 12)
    else:
      num = idx
    lines.extend([f"## {num}. {section.heading}", "", section.markdown_body, ""])
  return "\n".join(lines)
