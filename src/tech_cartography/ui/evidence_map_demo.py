"""Evidence Map demo mode — load existing outputs and render Streamlit UI (Phase 21.1)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.reports.project_export import load_records_csv
from tech_cartography.ui.easy_japanese_ui import (
  inject_easy_ui_css,
  render_caution_box,
  render_dataframe_stretch,
  render_info_box,
  render_metric_cards,
  render_warning_box,
)
from tech_cartography.ui.streamlit_session import DEMO_PUBLICATION_NUMBER

NOT_AVAILABLE = "not available"

ARTIFACT_RELATIVE_PATHS: dict[str, str] = {
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

DEFAULT_EVIDENCE_GAPS: tuple[str, ...] = (
  "BigQuery fulltext claims/description欠落",
  "Manual Claims Route",
  "description未入力",
  "examples未確認",
  "claims_only由来の限界",
  "CN/EP/JPはmanual route継続",
  "専門家レビューが必要",
)

DEFAULT_NEXT_ACTIONS: tuple[str, ...] = (
  "descriptionをmanualで追加する",
  "実施例・測定条件を確認する",
  "selected evidence papersを技術者が確認する",
  "Claim × Paper linksを専門家がレビューする",
  "CN/EP/JP Strategic Watch候補をmanual確認する",
  "追加1〜2件で再現性確認を行う",
)

SELECTED_PAPERS_COLUMNS: tuple[str, ...] = (
  "title",
  "doi",
  "source",
  "publication_year",
  "cited_by_count",
  "relevance_bucket",
  "evidence_role",
  "confidence",
)

CLAIM_LINKS_COLUMNS: tuple[str, ...] = (
  "claim_element",
  "claim_element_text",
  "paper_title",
  "title",
  "link_type",
  "confidence",
  "caveat",
  "evidence_role",
)

MARKET_SIGNAL_NOTICE = (
  "企業・市場シグナルは、現時点では手動入力または将来拡張の対象です。"
  "架空情報を本物のように表示することはしません。"
  'デモ用の仮想シグナルを使う場合は、必ず "Synthetic demo signal" と明記します。'
)


@dataclass
class EvidenceMapDemoArtifacts:
  publication_number: str
  status: str
  base_dir: Path
  evidence_map_md: str | None
  evidence_map_json: dict[str, Any] | None
  evidence_items_df: pd.DataFrame
  selected_papers_df: pd.DataFrame
  claim_paper_links_df: pd.DataFrame
  paper_relevance_report_md: str | None
  openalex_execution_summary_md: str | None
  missing_artifacts: list[str] = field(default_factory=list)
  errors: list[str] = field(default_factory=list)


def safe_read_text(path: Path) -> tuple[str | None, str]:
  if not path.exists():
    return None, f"file not found: {path}"
  try:
    return path.read_text(encoding="utf-8"), ""
  except OSError as exc:
    return None, f"read error ({path.name}): {exc}"


def safe_read_json(path: Path) -> tuple[dict[str, Any] | None, str]:
  text, err = safe_read_text(path)
  if err:
    return None, err
  if text is None:
    return None, f"empty file: {path}"
  try:
    parsed = json.loads(text)
    if isinstance(parsed, dict):
      return parsed, ""
    return None, f"json root is not object: {path.name}"
  except json.JSONDecodeError as exc:
    return None, f"json parse error ({path.name}): {exc}"


def safe_read_csv(path: Path) -> tuple[pd.DataFrame, str]:
  if not path.exists():
    return pd.DataFrame(), f"file not found: {path}"
  try:
    rows = load_records_csv(str(path))
    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    return _normalize_dataframe(df), ""
  except Exception as exc:
    return pd.DataFrame(), f"csv read error ({path.name}): {exc}"


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
  if df.empty:
    return df
  out = df.copy()
  for col in out.columns:
    out[col] = out[col].apply(_normalize_cell)
  return out


def _normalize_cell(value: Any) -> Any:
  if value is None:
    return ""
  if isinstance(value, float) and pd.isna(value):
    return ""
  if pd.isna(value):
    return ""
  return value


def _resolve_project_root(project_root: Path | str) -> Path:
  return Path(project_root).resolve()


def _compute_status(
  *,
  missing: list[str],
  errors: list[str],
  has_core: bool,
) -> str:
  if errors and not has_core:
    return "error"
  if not missing and not errors:
    return "ready"
  if len(missing) >= len(ARTIFACT_RELATIVE_PATHS):
    return "missing"
  if has_core:
    return "partial"
  if errors:
    return "error"
  return "missing"


def load_demo_evidence_map_artifacts(
  project_root: Path | str = ".",
  *,
  publication_number: str = DEMO_PUBLICATION_NUMBER,
) -> EvidenceMapDemoArtifacts:
  base_dir = _resolve_project_root(project_root)
  missing: list[str] = []
  errors: list[str] = []

  md_path = base_dir / ARTIFACT_RELATIVE_PATHS["evidence_map_synthesis_md"]
  json_path = base_dir / ARTIFACT_RELATIVE_PATHS["evidence_map_synthesis_json"]
  items_path = base_dir / ARTIFACT_RELATIVE_PATHS["evidence_map_items_csv"]
  papers_path = base_dir / ARTIFACT_RELATIVE_PATHS["selected_evidence_papers_csv"]
  links_path = base_dir / ARTIFACT_RELATIVE_PATHS["claim_paper_candidate_links_csv"]
  relevance_path = base_dir / ARTIFACT_RELATIVE_PATHS["paper_candidate_relevance_report_md"]
  openalex_path = base_dir / ARTIFACT_RELATIVE_PATHS["openalex_execution_summary_md"]

  evidence_map_md, md_err = safe_read_text(md_path)
  if md_err:
    if "not found" in md_err:
      missing.append("evidence_map_synthesis_md")
    else:
      errors.append(md_err)

  evidence_map_json, json_err = safe_read_json(json_path)
  if json_err:
    if "not found" in json_err:
      missing.append("evidence_map_synthesis_json")
    else:
      errors.append(json_err)

  evidence_items_df, items_err = safe_read_csv(items_path)
  if items_err:
    if "not found" in items_err:
      missing.append("evidence_map_items_csv")
    else:
      errors.append(items_err)

  selected_papers_df, papers_err = safe_read_csv(papers_path)
  if papers_err:
    if "not found" in papers_err:
      missing.append("selected_evidence_papers_csv")
    else:
      errors.append(papers_err)

  claim_paper_links_df, links_err = safe_read_csv(links_path)
  if links_err:
    if "not found" in links_err:
      missing.append("claim_paper_candidate_links_csv")
    else:
      errors.append(links_err)

  paper_relevance_report_md, rel_err = safe_read_text(relevance_path)
  if rel_err:
    if "not found" in rel_err:
      missing.append("paper_candidate_relevance_report_md")
    else:
      errors.append(rel_err)

  openalex_execution_summary_md, oa_err = safe_read_text(openalex_path)
  if oa_err:
    if "not found" in oa_err:
      missing.append("openalex_execution_summary_md")
    else:
      errors.append(oa_err)

  has_core = bool(
    evidence_map_md
    or evidence_map_json
    or not selected_papers_df.empty
    or not claim_paper_links_df.empty
  )
  status = _compute_status(missing=missing, errors=errors, has_core=has_core)

  return EvidenceMapDemoArtifacts(
    publication_number=publication_number,
    status=status,
    base_dir=base_dir,
    evidence_map_md=evidence_map_md,
    evidence_map_json=evidence_map_json,
    evidence_items_df=evidence_items_df,
    selected_papers_df=selected_papers_df,
    claim_paper_links_df=claim_paper_links_df,
    paper_relevance_report_md=paper_relevance_report_md,
    openalex_execution_summary_md=openalex_execution_summary_md,
    missing_artifacts=missing,
    errors=errors,
  )


def _select_existing_columns(df: pd.DataFrame, preferred: tuple[str, ...]) -> pd.DataFrame:
  if df.empty:
    return df
  cols = [c for c in preferred if c in df.columns]
  if cols:
    return df[cols]
  return df


def _summary_value(artifacts: EvidenceMapDemoArtifacts, key: str, fallback: Any = NOT_AVAILABLE) -> str:
  synthesis = artifacts.evidence_map_json or {}
  if isinstance(synthesis, dict) and synthesis.get(key) not in (None, ""):
    return str(synthesis.get(key))
  if key == "publication_number":
    return artifacts.publication_number
  if key == "selected_evidence_paper_count":
    return str(len(artifacts.selected_papers_df))
  if key == "claim_paper_link_count":
    return str(len(artifacts.claim_paper_links_df))
  if key == "retrieval_route":
    return "Manual Claims Route"
  if key == "evidence_level":
    return "claims_only / weak-to-medium supporting evidence candidate"
  if key == "claim_element_count" and not artifacts.evidence_items_df.empty:
    return str(len(artifacts.evidence_items_df))
  return str(fallback)


def render_demo_mode_banner(artifacts: EvidenceMapDemoArtifacts) -> None:
  st.markdown(inject_easy_ui_css(), unsafe_allow_html=True)
  title = f"デモモード: {artifacts.publication_number} Evidence Map"
  st.markdown(
    render_info_box(
      f"{title}<br>"
      "このデモは既存outputsを読み込んで表示しています。新しいAPI実行は行っていません。"
      f"<br>status: {artifacts.status}"
    ),
    unsafe_allow_html=True,
  )
  if artifacts.missing_artifacts:
    st.markdown(
      render_warning_box(
        "一部の成果物が見つかりませんでした。ただし、利用可能な成果物だけで表示を継続します。"
        f"<br>missing: {', '.join(artifacts.missing_artifacts)}"
      ),
      unsafe_allow_html=True,
    )
  if artifacts.errors:
    with st.expander("読み込みエラー（デバッグ）"):
      for err in artifacts.errors:
        st.caption(err)


def render_demo_story_cards() -> str:
  card1 = (
    '<div class="tc-card-box">'
    "<strong>Tech Cartographyがやること</strong><ul>"
    "<li>特許候補を集める</li>"
    "<li>読むべき特許を選ぶ</li>"
    "<li>請求項から技術要素を抽出する</li>"
    "<li>論文候補と対応づける</li>"
    "<li>Evidence GapとNext Actionsを出す</li>"
    "</ul></div>"
  )
  card2 = (
    '<div class="tc-card-box">'
    "<strong>今回のDeep Dive対象</strong><ul>"
    f"<li>Publication: {DEMO_PUBLICATION_NUMBER}</li>"
    "<li>Route: Manual Claims Route</li>"
    "<li>Status: Evidence Map ready</li>"
    "<li>Note: BigQueryに公報行は存在したが、claims/descriptionが空だったためManual Routeへ切り替え</li>"
    "</ul></div>"
  )
  card3 = (
    '<div class="tc-caution-box">'
    "<strong>重要な注意</strong><ul>"
    "<li>論文は特許主張の証明ではなくsupporting evidence candidate</li>"
    "<li>claims_only由来のためconfidenceは最大medium、基本はlow/weak</li>"
    "<li>FTO、侵害、有効性判断はしない</li>"
    "<li>最終判断には専門家レビューが必要</li>"
    "<li>架空情報を本物のように見せない</li>"
    "</ul></div>"
  )
  return card1 + card2 + card3


def render_evidence_map_summary(artifacts: EvidenceMapDemoArtifacts) -> None:
  st.subheader("Evidence Map Summary")
  metrics = [
    {"label": "publication_number", "value": _summary_value(artifacts, "publication_number")},
    {"label": "synthesis_status", "value": _summary_value(artifacts, "synthesis_status")},
    {"label": "retrieval_route", "value": _summary_value(artifacts, "retrieval_route")},
    {"label": "claim_element_count", "value": _summary_value(artifacts, "claim_element_count")},
    {
      "label": "selected_evidence_paper_count",
      "value": _summary_value(artifacts, "selected_evidence_paper_count"),
    },
    {"label": "claim_paper_link_count", "value": _summary_value(artifacts, "claim_paper_link_count")},
    {"label": "evidence_level", "value": _summary_value(artifacts, "evidence_level")},
    {"label": "caveat", "value": _summary_value(artifacts, "caveat")},
  ]
  st.markdown(render_metric_cards(metrics), unsafe_allow_html=True)
  caveat = _summary_value(artifacts, "caveat_japanese", "")
  if caveat and caveat != NOT_AVAILABLE:
    st.markdown(render_caution_box(caveat), unsafe_allow_html=True)


def render_selected_evidence_papers(artifacts: EvidenceMapDemoArtifacts) -> None:
  st.subheader("Selected Evidence Papers")
  st.markdown(
    render_info_box(
      "論文は特許主張の証明ではなく、"
      "技術背景を確認するためのsupporting evidence candidateです。"
    ),
    unsafe_allow_html=True,
  )
  df = _select_existing_columns(artifacts.selected_papers_df, SELECTED_PAPERS_COLUMNS)
  if df.empty:
    st.info("Selected Evidence Papers の成果物がまだありません。")
    return
  render_dataframe_stretch(df, hide_index=True)


def render_claim_paper_links(artifacts: EvidenceMapDemoArtifacts) -> None:
  st.subheader("Claim × Paper Candidate Links")
  st.markdown(
    render_caution_box(
      "claims_only由来のため、この対応はweak / low / medium confidenceとして扱います。"
    ),
    unsafe_allow_html=True,
  )
  df = _select_existing_columns(artifacts.claim_paper_links_df, CLAIM_LINKS_COLUMNS)
  if df.empty:
    st.info("Claim × Paper Candidate Links の成果物がまだありません。")
    return
  render_dataframe_stretch(df, hide_index=True)


def _extract_list_from_synthesis(
  synthesis: dict[str, Any] | None,
  *keys: str,
) -> list[str]:
  if not isinstance(synthesis, dict):
    return []
  for key in keys:
    value = synthesis.get(key)
    if isinstance(value, list):
      return [str(item) for item in value if item]
    if isinstance(value, str) and value.strip():
      return [line.strip("- ").strip() for line in value.splitlines() if line.strip()]
  return []


def render_evidence_gaps_and_next_actions(artifacts: EvidenceMapDemoArtifacts) -> None:
  synthesis = artifacts.evidence_map_json or {}
  gaps = _extract_list_from_synthesis(synthesis, "evidence_gaps", "gaps")
  actions = _extract_list_from_synthesis(synthesis, "next_actions", "recommended_next_actions")
  if not gaps:
    gaps = list(DEFAULT_EVIDENCE_GAPS)
  if not actions:
    actions = list(DEFAULT_NEXT_ACTIONS)

  st.subheader("Evidence Gaps")
  gap_html = "".join(f"<li>{gap}</li>" for gap in gaps)
  st.markdown(f'<div class="tc-warning-box"><ul>{gap_html}</ul></div>', unsafe_allow_html=True)

  st.subheader("Next Actions")
  action_html = "".join(f"<li>{action}</li>" for action in actions)
  st.markdown(f'<div class="tc-card-box"><ul>{action_html}</ul></div>', unsafe_allow_html=True)

  if artifacts.evidence_map_md:
    with st.expander("Evidence Map Synthesis（Markdown抜粋）"):
      st.markdown(artifacts.evidence_map_md[:8000])


def render_evidence_map_report(artifacts: EvidenceMapDemoArtifacts) -> None:
  st.subheader("Evidence Map レポート")
  if artifacts.evidence_map_md:
    st.markdown(artifacts.evidence_map_md)
  else:
    st.info("evidence_map_synthesis.md が見つかりません。")

  if artifacts.paper_relevance_report_md:
    with st.expander("Paper Candidate Relevance Report"):
      st.markdown(artifacts.paper_relevance_report_md)
  else:
    with st.expander("Paper Candidate Relevance Report"):
      st.caption("paper_candidate_relevance_report.md は not available です。")

  if artifacts.openalex_execution_summary_md:
    with st.expander("OpenAlex Execution Summary"):
      st.markdown(artifacts.openalex_execution_summary_md)
  else:
    with st.expander("OpenAlex Execution Summary"):
      st.caption("openalex_execution_summary.md は not available です。")


def render_market_signal_demo_notice() -> None:
  st.markdown(render_info_box(MARKET_SIGNAL_NOTICE), unsafe_allow_html=True)


def render_demo_evidence_tab(artifacts: EvidenceMapDemoArtifacts) -> None:
  st.markdown(
    render_caution_box(
      "論文候補は証明ではありません。FTO、侵害、有効性判断はしません。専門家レビューが必要です。"
    ),
    unsafe_allow_html=True,
  )
  render_evidence_map_summary(artifacts)
  render_selected_evidence_papers(artifacts)
  render_claim_paper_links(artifacts)
  render_evidence_gaps_and_next_actions(artifacts)
  if not artifacts.evidence_items_df.empty:
    with st.expander("Evidence Map Items"):
      render_dataframe_stretch(artifacts.evidence_items_df.head(50), hide_index=True)


def render_demo_start_tab(artifacts: EvidenceMapDemoArtifacts) -> None:
  st.markdown(render_demo_story_cards(), unsafe_allow_html=True)
  st.markdown(
    render_info_box(
      f"デモ run_id: demo_us_12565719_b2 / status: {artifacts.status} / "
      "BigQuery・OpenAlexの新規実行は行っていません。"
    ),
    unsafe_allow_html=True,
  )
