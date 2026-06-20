"""Demo output bundle path resolution for Cloud Run (Phase 24.6A)."""

from __future__ import annotations

import os
from pathlib import Path

DEMO_OUTPUTS_ROOT_ENV = "DEMO_OUTPUTS_ROOT"
DEMO_PUBLICATION_NUMBER = "US-12565719-B2"
DEFAULT_DEMO_OUTPUTS_ROOT = "demo_outputs"

REQUIRED_BUNDLE_FILES: tuple[str, ...] = (
  "evidence_map_synthesis.md",
  "evidence_map_synthesis.json",
  "evidence_map_items.csv",
  "selected_evidence_papers.csv",
  "claim_paper_candidate_links.csv",
  "paper_candidate_relevance_report.md",
  "openalex_execution_summary.md",
  "web_signal_review_pack.json",
  "strategic_watch_brief.md",
  "top_strategic_watch_items.csv",
  "weekly_digest_preview_US-12565719-B2.md",
  "intelligence_report_US-12565719-B2.md",
  "final_end_to_end_validation_summary.json",
)

BUNDLE_COPY_SOURCES: tuple[tuple[str, str], ...] = (
  (
    "outputs/evidence_map_synthesis/US-12565719-B2/evidence_map_synthesis.md",
    "evidence_map_synthesis.md",
  ),
  (
    "outputs/evidence_map_synthesis/US-12565719-B2/evidence_map_synthesis.json",
    "evidence_map_synthesis.json",
  ),
  (
    "outputs/evidence_map_synthesis/US-12565719-B2/evidence_map_items.csv",
    "evidence_map_items.csv",
  ),
  (
    "outputs/openalex_limited_execution/selected_evidence_papers.csv",
    "selected_evidence_papers.csv",
  ),
  (
    "outputs/openalex_limited_execution/claim_paper_candidate_links.csv",
    "claim_paper_candidate_links.csv",
  ),
  (
    "outputs/openalex_limited_execution/paper_candidate_relevance_report.md",
    "paper_candidate_relevance_report.md",
  ),
  (
    "outputs/openalex_limited_execution/openalex_execution_summary.md",
    "openalex_execution_summary.md",
  ),
  (
    "outputs/web_signals/tavily_pan_carbon_fiber/review_pack/web_signal_review_pack.json",
    "web_signal_review_pack.json",
  ),
  (
    "outputs/web_signals/tavily_pan_carbon_fiber/review_pack/web_signal_review_items.csv",
    "web_signal_review_items.csv",
  ),
  (
    "outputs/web_signals/tavily_pan_carbon_fiber/review_pack/high_priority_web_signals.csv",
    "high_priority_web_signals.csv",
  ),
  (
    "outputs/web_signals/tavily_pan_carbon_fiber/review_pack/ir_disclosure_candidates.csv",
    "ir_disclosure_candidates.csv",
  ),
  (
    "outputs/web_signals/tavily_pan_carbon_fiber/review_pack/money_national_project_candidates.csv",
    "money_national_project_candidates.csv",
  ),
  (
    "outputs/web_signals/tavily_pan_carbon_fiber/review_pack/company_local_news_candidates.csv",
    "company_local_news_candidates.csv",
  ),
  (
    "outputs/web_signals/tavily_pan_carbon_fiber/review_pack/rejected_or_low_quality_sources.csv",
    "rejected_or_low_quality_sources.csv",
  ),
  (
    "outputs/web_signals/tavily_pan_carbon_fiber/review_pack/web_signal_review_summary.md",
    "web_signal_review_summary.md",
  ),
  (
    "outputs/strategic_watch_briefs/US-12565719-B2/strategic_watch_brief.md",
    "strategic_watch_brief.md",
  ),
  (
    "outputs/strategic_watch_briefs/US-12565719-B2/strategic_watch_brief.json",
    "strategic_watch_brief.json",
  ),
  (
    "outputs/strategic_watch_briefs/US-12565719-B2/strategic_watch_items.csv",
    "strategic_watch_items.csv",
  ),
  (
    "outputs/strategic_watch_briefs/US-12565719-B2/top_strategic_watch_items.csv",
    "top_strategic_watch_items.csv",
  ),
  (
    "outputs/strategic_watch_briefs/US-12565719-B2/strategic_watch_next_actions.md",
    "strategic_watch_next_actions.md",
  ),
  (
    "outputs/delivery/weekly_digest_preview_US-12565719-B2.md",
    "weekly_digest_preview_US-12565719-B2.md",
  ),
  (
    "outputs/delivery/weekly_digest_preview_US-12565719-B2.html",
    "weekly_digest_preview_US-12565719-B2.html",
  ),
  (
    "outputs/delivery/digest_diff_US-12565719-B2.md",
    "digest_diff_US-12565719-B2.md",
  ),
  (
    "outputs/delivery/intelligence_report_US-12565719-B2.md",
    "intelligence_report_US-12565719-B2.md",
  ),
  ("outputs/delivery/overview_page.md", "overview_page.md"),
  (
    "outputs/validation/final_validation/final_end_to_end_validation_summary.json",
    "final_end_to_end_validation_summary.json",
  ),
  (
    "outputs/delivery/tech_cartography_report_bundle_US-12565719-B2.zip",
    "tech_cartography_report_bundle_US-12565719-B2.zip",
  ),
)

LEGACY_EVIDENCE_MAP_PATHS: dict[str, str] = {
  "evidence_map_synthesis_md": (
    "outputs/evidence_map_synthesis/US-12565719-B2/evidence_map_synthesis.md"
  ),
  "evidence_map_synthesis_json": (
    "outputs/evidence_map_synthesis/US-12565719-B2/evidence_map_synthesis.json"
  ),
  "evidence_map_items_csv": (
    "outputs/evidence_map_synthesis/US-12565719-B2/evidence_map_items.csv"
  ),
  "selected_evidence_papers_csv": "outputs/openalex_limited_execution/selected_evidence_papers.csv",
  "claim_paper_candidate_links_csv": (
    "outputs/openalex_limited_execution/claim_paper_candidate_links.csv"
  ),
  "paper_candidate_relevance_report_md": (
    "outputs/openalex_limited_execution/paper_candidate_relevance_report.md"
  ),
  "openalex_execution_summary_md": (
    "outputs/openalex_limited_execution/openalex_execution_summary.md"
  ),
}


def demo_outputs_root_name() -> str | None:
  raw = os.environ.get(DEMO_OUTPUTS_ROOT_ENV, "").strip()
  return raw or None


def uses_demo_outputs_bundle() -> bool:
  return demo_outputs_root_name() is not None


def demo_bundle_dir(project_root: Path | str, *, publication_number: str = DEMO_PUBLICATION_NUMBER) -> Path:
  root = Path(project_root).resolve()
  bundle_root = demo_outputs_root_name() or DEFAULT_DEMO_OUTPUTS_ROOT
  return root / bundle_root / publication_number


def bundle_file_path(
  project_root: Path | str,
  bundle_filename: str,
  *,
  publication_number: str = DEMO_PUBLICATION_NUMBER,
) -> Path:
  return demo_bundle_dir(project_root, publication_number=publication_number) / bundle_filename


def resolve_bundle_or_legacy(
  project_root: Path | str,
  bundle_filename: str,
  legacy_relative: str,
  *,
  publication_number: str = DEMO_PUBLICATION_NUMBER,
) -> Path:
  root = Path(project_root).resolve()
  if uses_demo_outputs_bundle():
    return bundle_file_path(root, bundle_filename, publication_number=publication_number)
  legacy = root / legacy_relative
  if legacy.exists():
    return legacy
  bundled = bundle_file_path(root, bundle_filename, publication_number=publication_number)
  if bundled.exists():
    return bundled
  return legacy


def resolve_demo_data_dir(
  project_root: Path | str,
  *,
  legacy_relative_dir: str,
  publication_number: str = DEMO_PUBLICATION_NUMBER,
) -> Path:
  root = Path(project_root).resolve()
  if uses_demo_outputs_bundle():
    return demo_bundle_dir(root, publication_number=publication_number)
  legacy = root / legacy_relative_dir
  if legacy.exists():
    return legacy
  bundled = demo_bundle_dir(root, publication_number=publication_number)
  if bundled.exists():
    return bundled
  return legacy


def missing_bundle_files(project_root: Path | str) -> list[str]:
  bundle_dir = demo_bundle_dir(project_root)
  missing: list[str] = []
  for filename in REQUIRED_BUNDLE_FILES:
    if not (bundle_dir / filename).exists():
      missing.append(filename)
  return missing


def relative_upload_path(bundle_filename: str) -> str:
  return f"{DEFAULT_DEMO_OUTPUTS_ROOT}/{DEMO_PUBLICATION_NUMBER}/{bundle_filename}"
