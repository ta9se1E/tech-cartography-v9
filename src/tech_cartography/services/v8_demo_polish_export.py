"""v8 Demo Polish export (Phase 27L)."""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

from tech_cartography.runtime.live_artifact_paths import get_live_outputs_root
from tech_cartography.runtime.v8_demo_polish_schema import (
  DEMO_POLISH_NEXT_PHASES,
  DEMO_POLISH_SAFETY_NOTICES,
  V8DemoPolishExport,
  V8DemoPolishReport,
  V8DemoStoryCard,
)

V8_DEMO_POLISH_SUBDIR = "v8_demo_polish"
LOCAL_V8_DEMO_POLISH_SUBDIR = "local_v8_demo_polish"

_SENSITIVE_RE = re.compile(
  r"(smtp_password|tavily_api_key|api[_-]?key\s*[:=]|authorization|oauth|jwt|eyJhbGci)",
  re.IGNORECASE,
)

STORY_CARD_CSV_COLUMNS: tuple[str, ...] = (
  "card_id",
  "case_id",
  "card_title",
  "card_subtitle",
  "card_type",
  "key_message",
  "action_hint",
  "caution_text",
  "display_priority",
)


def get_demo_polish_dir(project_root: Path | str | None = None) -> Path:
  root = get_live_outputs_root(project_root)
  if root.name == "outputs" or not str(root).endswith("live"):
    return root / LOCAL_V8_DEMO_POLISH_SUBDIR
  return root / V8_DEMO_POLISH_SUBDIR


def find_latest_demo_polish_dir(
  case_id: str | None = None,
  project_root: Path | str | None = None,
) -> Path | None:
  base = get_demo_polish_dir(project_root)
  if not base.is_dir():
    return None
  if case_id:
    dirs = sorted(
      (p for p in base.iterdir() if p.is_dir() and case_id in p.name),
      key=lambda p: p.stat().st_mtime,
      reverse=True,
    )
    return dirs[0] if dirs else None
  dirs = sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
  return dirs[0] if dirs else None


def _assert_no_secrets(text: str) -> None:
  if _SENSITIVE_RE.search(text):
    raise ValueError("export content must not contain secret-like strings")


def story_cards_to_csv(cards: list[V8DemoStoryCard]) -> str:
  buffer = io.StringIO()
  writer = csv.DictWriter(buffer, fieldnames=list(STORY_CARD_CSV_COLUMNS))
  writer.writeheader()
  for card in cards:
    writer.writerow({
      "card_id": card.card_id,
      "case_id": card.case_id,
      "card_title": card.card_title,
      "card_subtitle": card.card_subtitle,
      "card_type": card.card_type,
      "key_message": card.key_message,
      "action_hint": card.action_hint,
      "caution_text": card.caution_text,
      "display_priority": card.display_priority,
    })
  return buffer.getvalue()


def caveats_markdown() -> str:
  lines = [
    "# Demo Caveats",
    "",
    "## Safety",
    *[f"- {n}" for n in DEMO_POLISH_SAFETY_NOTICES],
    "",
    "## Next Phases",
    *[f"- {p}" for p in DEMO_POLISH_NEXT_PHASES],
  ]
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def report_to_markdown(report: V8DemoPolishReport) -> str:
  ev = report.evidence_demo_status
  gap = report.gap_demo_status
  lines = [
    "# Demo Polish Report",
    "",
    f"- report_id: {report.report_id}",
    f"- case_id: {report.case_id}",
    f"- publication_number: {report.publication_number}",
    f"- generated_at: {report.generated_at}",
    "",
    "## Demo Story",
    report.demo_narrative,
    "",
    "## 1000件母集団 → Top5",
    f"- {report.large_candidate_summary}",
    f"- {report.patent_shortlist_summary}",
    "",
  ]
  if ev:
    lines.extend([
      "## Claim Status",
      f"- claim_text_status: {ev.claim_text_status}",
      f"- claim_text_required_count: {ev.claim_text_required_count}",
      f"- manual_claim_count: {ev.manual_claim_count}",
      f"- before_after: {report.before_after_claim_status}",
      "",
      "## Evidence Candidate Summary",
      f"- evidence_link_count: {ev.evidence_link_count}",
      f"- paper_candidate_count: {ev.paper_candidate_count}",
      f"- web_candidate_count: {ev.web_candidate_count}",
      f"- company_candidate_count: {ev.company_candidate_count}",
      f"- missing_evidence_count: {ev.missing_evidence_count}",
      f"- needs_human_review_count: {ev.needs_human_review_count}",
      f"- strongest: {ev.strongest_candidate_summary}",
      f"- weakest: {ev.weakest_point_summary}",
      "",
    ])
  if gap:
    lines.extend([
      "## Gap Summary",
      f"- gap_count: {gap.gap_count}",
      f"- top_gap_types: {', '.join(gap.top_gap_types)}",
      f"- claim_text_gap_count: {gap.claim_text_gap_count}",
      f"- example_support_gap_count: {gap.example_support_gap_count}",
      f"- paper_support_gap_count: {gap.paper_support_gap_count}",
      "",
      "## Top 3 Next Actions",
      *[f"- {a}" for a in gap.top_3_next_actions],
      "",
    ])
  lines.extend([
    "## Fixed Point Observation Summary",
    f"- no_email_send: {report.no_email_send}",
    f"- no_scheduler_start: {report.no_scheduler_start}",
    "",
    "## Remaining Limitations",
    *[f"- {lim}" for lim in report.remaining_limitations],
    "",
    "## Artifact Trace",
    *[f"- {p}" for p in report.artifact_trace],
    "",
    "## Safety",
    *[f"- {n}" for n in DEMO_POLISH_SAFETY_NOTICES],
  ])
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def export_demo_polish(
  report: V8DemoPolishReport,
  *,
  project_root: Path | str | None = None,
) -> V8DemoPolishExport:
  root = Path(project_root) if project_root else Path.cwd()
  slug = report.generated_at.replace(":", "").replace("-", "").replace("+00:00", "Z")
  output_dir = get_demo_polish_dir(root) / f"polish_{report.case_id}_{slug}"
  output_dir.mkdir(parents=True, exist_ok=True)

  json_path = output_dir / "demo_polish_report.json"
  md_path = output_dir / "demo_polish_report.md"
  manifest_path = output_dir / "demo_polish_manifest.json"
  story_csv_path = output_dir / "demo_story_cards.csv"
  narrative_path = output_dir / "demo_narrative.md"
  caveats_path = output_dir / "demo_caveats.md"

  json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
  md_path.write_text(report_to_markdown(report), encoding="utf-8")
  narrative_path.write_text(report.demo_narrative + "\n", encoding="utf-8")
  caveats_path.write_text(caveats_markdown(), encoding="utf-8")
  story_csv_path.write_text(story_cards_to_csv(report.story_cards), encoding="utf-8")

  ev = report.evidence_demo_status
  gap = report.gap_demo_status
  manifest = {
    "export_id": report.report_id,
    "case_id": report.case_id,
    "publication_number": report.publication_number,
    "claim_text_required_count": ev.claim_text_required_count if ev else 0,
    "manual_claim_count": ev.manual_claim_count if ev else 0,
    "evidence_link_count": ev.evidence_link_count if ev else 0,
    "gap_count": gap.gap_count if gap else 0,
    "top_3_next_actions": gap.top_3_next_actions if gap else [],
    "remaining_limitations": report.remaining_limitations,
    "safety_notices": list(DEMO_POLISH_SAFETY_NOTICES),
    "files": {
      "demo_polish_report_json": str(json_path),
      "demo_polish_report_md": str(md_path),
      "demo_story_cards_csv": str(story_csv_path),
      "demo_narrative_md": str(narrative_path),
      "demo_caveats_md": str(caveats_path),
    },
  }
  manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2)
  _assert_no_secrets(manifest_text)
  manifest_path.write_text(manifest_text, encoding="utf-8")

  report.export_paths = [
    str(json_path),
    str(md_path),
    str(manifest_path),
    str(story_csv_path),
    str(narrative_path),
    str(caveats_path),
  ]

  return V8DemoPolishExport(
    export_id=report.report_id,
    output_dir=str(output_dir),
    json_path=str(json_path),
    md_path=str(md_path),
    manifest_path=str(manifest_path),
    story_cards_csv_path=str(story_csv_path),
    narrative_path=str(narrative_path),
    caveats_path=str(caveats_path),
    created_at=report.generated_at,
  )
