"""Evidence Map demo mode — load existing outputs and render Streamlit UI (Phase 21.1–21.2)."""

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
from tech_cartography.ui.label_renderer import (
  POLISHED_EVIDENCE_GAPS,
  POLISHED_NEXT_ACTIONS,
  format_paper_link_markdown,
  resolve_paper_url,
  translate_label,
)

NOT_AVAILABLE = "not available"
TITLE_MAX_LEN = 120
EVIDENCE_LEVEL_LABEL = "claims_only / weak-to-medium"
ROUTE_LABEL = "Manual Claims Route"

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

from tech_cartography.ui.streamlit_session import DEMO_PUBLICATION_NUMBER

# Backward-compatible aliases (Phase 24.5B polished lists)
FIXED_EVIDENCE_GAPS: tuple[str, ...] = POLISHED_EVIDENCE_GAPS
FIXED_NEXT_ACTIONS: tuple[str, ...] = POLISHED_NEXT_ACTIONS

# Backward-compatible aliases for tests / older imports
DEFAULT_EVIDENCE_GAPS = FIXED_EVIDENCE_GAPS
DEFAULT_NEXT_ACTIONS = FIXED_NEXT_ACTIONS

SELECTED_PAPERS_COLUMNS: tuple[str, ...] = (
  "title",
  "doi",
  "論文を開く",
  "source",
  "publication_year",
  "cited_by_count",
  "relevance_bucket",
  "evidence_role",
  "confidence",
)

CLAIM_LINKS_DISPLAY_COLUMNS: tuple[str, ...] = (
  "claim_element",
  "claim_element_text",
  "paper_display",
  "論文を開く",
  "link_type",
  "confidence",
  "caveat",
  "evidence_role",
)

EVIDENCE_MAP_READING_GUIDE = (
  "このEvidence Mapは、特許請求項から抽出した技術要素と、OpenAlex由来の論文候補を対応づけたものです。"
  "論文候補は特許主張の証明ではなく、技術背景を確認するための supporting evidence candidate です。"
  "claims_only由来のため、明細書・実施例・測定条件の確認は未完了です。"
)

EXECUTIVE_SUMMARY_TEXT = (
  f"{DEMO_PUBLICATION_NUMBER}について、BigQuery fulltextではclaims/descriptionが取得できなかったため、"
  "Manual Claims Routeに切り替えました。"
  "manual claimsから技術要素を抽出し、OpenAlex由来の論文候補と対応づけたEvidence Mapを生成しています。"
  "ただし、この分析はclaims_only由来であり、論文候補はsupporting evidence candidateです。"
  "FTO、侵害、有効性判断ではありません。"
)

MARKET_SIGNAL_NOTICE = (
  "企業・市場シグナルは、現時点では手動入力または将来拡張の対象です。"
  "架空情報を本物のように表示することはしません。"
  'デモ用の仮想シグナルを使う場合は、必ず "Synthetic demo signal" と明記します。'
  "このタブは将来的に Strategic Watch Brief として、"
  "Patent signal / Paper signal / Company signal / Hypothesis / Confidence / "
  "Next verification action を整理する予定です。"
)

SELECTED_PAPERS_NOTICE = (
  "論文は supporting evidence candidate であり、特許主張を証明するものではありません。"
)

CLAIM_LINKS_NOTICE = (
  "この対応は claims_only 由来であり、weak / low / medium confidence の候補対応です。"
  "最終判断には専門家レビューが必要です。"
)

CLAIM_ELEMENT_MISSING_GUIDANCE = (
  "請求項要素の詳細テキストは未取得です。"
  "現在はManual Claims由来の限定的な対応候補として、選定論文を表示しています。"
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


def _is_empty_value(value: Any) -> bool:
  if value is None:
    return True
  if isinstance(value, float) and pd.isna(value):
    return True
  if pd.isna(value):
    return True
  return str(value).strip() == ""


def _truncate_title(text: str, max_len: int = TITLE_MAX_LEN) -> str:
  cleaned = str(text or "").strip()
  if len(cleaned) <= max_len:
    return cleaned
  return cleaned[: max_len - 1] + "…"


def _format_status_label(status: str) -> str:
  mapping = {
    "ready": "Evidence Map ready",
    "partial": "Evidence Map partial",
    "missing": "Evidence Map missing",
    "error": "Evidence Map error",
  }
  return mapping.get(status, f"Evidence Map {status}")


def _format_cited_by_count(value: Any) -> str:
  if _is_empty_value(value):
    return NOT_AVAILABLE
  try:
    number = int(float(value))
    return str(number)
  except (TypeError, ValueError):
    return str(value).strip() or NOT_AVAILABLE


def _is_missing_claim_field(value: Any) -> bool:
  if _is_empty_value(value):
    return True
  text = str(value).strip().lower()
  return text in {NOT_AVAILABLE.lower(), "n/a", "none", "nan", "unknown", "(none)"}


def filter_claim_paper_link_rows(df: pd.DataFrame | None) -> pd.DataFrame:
  """Drop rows whose claim element fields are empty or not available (Phase 24.5F)."""
  if df is None or df.empty:
    return pd.DataFrame()
  kept_rows: list[dict[str, Any]] = []
  for _, row in df.iterrows():
    row_dict = {str(k): _normalize_cell(v) for k, v in row.to_dict().items()}
    if _is_missing_claim_field(row_dict.get("claim_element")):
      continue
    if _is_missing_claim_field(row_dict.get("claim_element_text")):
      continue
    kept_rows.append(row.to_dict())
  return pd.DataFrame(kept_rows) if kept_rows else pd.DataFrame()


def _format_display_value(value: Any, *, default: str = NOT_AVAILABLE) -> str:
  if _is_empty_value(value):
    return default
  return str(value).strip()


def _format_link_type(value: Any) -> str:
  text = str(value or "").strip().lower()
  if not text:
    return NOT_AVAILABLE
  if text in {"fallback", "fallback_link", "weak_fallback"}:
    return "弱い対応 (fallback)"
  return str(value).strip()


def _format_confidence(value: Any) -> str:
  if _is_empty_value(value):
    return "low / weak"
  return str(value).strip()


def prepare_selected_papers_display_df(df: pd.DataFrame | None) -> pd.DataFrame:
  """Format selected papers for display; safe on empty / missing columns / NaN."""
  if df is None or df.empty:
    return pd.DataFrame(columns=list(SELECTED_PAPERS_COLUMNS))

  rows: list[dict[str, str]] = []
  for _, row in df.iterrows():
    row_dict = {str(k): _normalize_cell(v) for k, v in row.to_dict().items()}
    rows.append(
      {
        "title": _truncate_title(_format_display_value(row_dict.get("title"), default="(no title)")),
        "doi": _format_display_value(row_dict.get("doi")),
        "論文を開く": format_paper_link_markdown(resolve_paper_url(row_dict)),
        "source": _format_display_value(row_dict.get("source")),
        "publication_year": _format_display_value(row_dict.get("publication_year")),
        "cited_by_count": _format_cited_by_count(row_dict.get("cited_by_count")),
        "relevance_bucket": translate_label(row_dict.get("relevance_bucket")),
        "evidence_role": translate_label(
          row_dict.get("evidence_role") or row_dict.get("recommended_evidence_role"),
        ),
        "confidence": translate_label(row_dict.get("confidence"), default="低"),
      },
    )
  return pd.DataFrame(rows, columns=list(SELECTED_PAPERS_COLUMNS))


def prepare_claim_paper_links_display_df(df: pd.DataFrame | None) -> pd.DataFrame:
  """Format claim × paper links for display; safe on empty / missing columns / NaN."""
  if df is None or df.empty:
    return pd.DataFrame(columns=list(CLAIM_LINKS_DISPLAY_COLUMNS))

  rows: list[dict[str, str]] = []
  for _, row in df.iterrows():
    row_dict = {str(k): _normalize_cell(v) for k, v in row.to_dict().items()}
    paper_title_raw = row_dict.get("paper_title")
    title_raw = row_dict.get("title")
    if not _is_empty_value(paper_title_raw):
      paper_display = str(paper_title_raw).strip()
    elif not _is_empty_value(title_raw):
      paper_display = str(title_raw).strip()
    else:
      paper_display = "(no paper title)"

    claim_text = _format_display_value(row_dict.get("claim_element_text"), default="")
    if claim_text == NOT_AVAILABLE:
      claim_text = ""

    rows.append(
      {
        "claim_element": _format_display_value(row_dict.get("claim_element")),
        "claim_element_text": claim_text or NOT_AVAILABLE,
        "paper_display": _truncate_title(paper_display),
        "論文を開く": format_paper_link_markdown(resolve_paper_url(row_dict)),
        "link_type": _format_link_type(row_dict.get("link_type")),
        "confidence": translate_label(row_dict.get("confidence"), default="低"),
        "caveat": _format_display_value(row_dict.get("caveat") or row_dict.get("caveat_japanese")),
        "evidence_role": translate_label(row_dict.get("evidence_role")),
      },
    )
  return pd.DataFrame(rows, columns=list(CLAIM_LINKS_DISPLAY_COLUMNS))


def build_evidence_map_summary_metrics(artifacts: EvidenceMapDemoArtifacts) -> list[dict[str, str]]:
  """Build summary metric cards for the Evidence Map demo tab."""
  return [
    {"label": "今回詳しく読む特許", "value": artifacts.publication_number},
    {"label": "取得ルート", "value": translate_label(ROUTE_LABEL)},
    {"label": "Selected Evidence Papers", "value": str(len(artifacts.selected_papers_df))},
    {"label": "Claim × Paper Links", "value": str(len(artifacts.claim_paper_links_df))},
    {"label": "Evidence Level", "value": translate_label(EVIDENCE_LEVEL_LABEL)},
    {"label": "Status", "value": translate_label(_format_status_label(artifacts.status))},
  ]


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


def get_fixed_evidence_gaps(synthesis: dict[str, Any] | None = None) -> list[str]:
  """Return polished Evidence Gaps list (Phase 24.5B — no duplicate merge)."""
  _ = synthesis
  return list(POLISHED_EVIDENCE_GAPS)


def get_fixed_next_actions(synthesis: dict[str, Any] | None = None) -> list[str]:
  """Return polished Next Actions list (Phase 24.5B — no duplicate merge)."""
  _ = synthesis
  return list(POLISHED_NEXT_ACTIONS)


def render_evidence_map_reading_guide() -> str:
  return render_info_box(EVIDENCE_MAP_READING_GUIDE)


def render_executive_summary() -> str:
  return render_info_box(f"<strong>Executive Summary</strong><br>{EXECUTIVE_SUMMARY_TEXT}")


def render_three_minute_demo_guide() -> str:
  steps = [
    "はじめる: ツールの目的と見る順番",
    "技術の裏取り: Evidence Map Summary",
    "技術の裏取り: Selected Evidence Papers（論文リンク付き）",
    "技術の裏取り: Claim × Paper Links",
    "技術の裏取り: Evidence Gaps / Next Actions",
    "企業・市場シグナル: Web・公的プロジェクト候補",
    "レポート: 共有用まとめ",
  ]
  items = "".join(f"<li>{step}</li>" for step in steps)
  return (
    '<div class="tc-card-box">'
    "<strong>3分デモの見方</strong><ol>"
    f"{items}"
    "</ol>"
    "審査員・初見ユーザー向け: 上から順に見ると、"
    "「読むべき特許」と「次に確認すべきギャップ」が一目で分かります。"
    "</div>"
  )


def render_where_to_look_card() -> str:
  return (
    '<div class="tc-card-box">'
    "<strong>どこを見れば何が分かるか</strong><ul>"
    "<li><strong>技術の裏取り</strong>: 請求項と論文候補の対応</li>"
    "<li><strong>企業・市場シグナル</strong>: Web・公的プロジェクト・企業情報の確認候補</li>"
    "<li><strong>レポート</strong>: 共有用のまとめと次アクション</li>"
    "<li><strong>本番実行</strong>: 新しいテーマの分析（サイドバーで切り替え）</li>"
    "</ul></div>"
  )


def render_ui_mode_guide_card(*, include_developer_mode: bool | None = None) -> str:
  if include_developer_mode is None:
    from tech_cartography.ui.developer_mode_visibility import is_show_developer_mode_enabled

    include_developer_mode = is_show_developer_mode_enabled()
  items = [
    "<li><strong>デモを見る</strong>: 完成済み成果物を読むだけ（デフォルト）</li>",
    "<li><strong>本番実行</strong>: 新しいテーマでテーマ入力・Manual Claims・E2E Chain</li>",
  ]
  if include_developer_mode:
    items.append(
      "<li><strong>開発者向け</strong>: 実行ID・paths・validation 参照（折りたたみ内）</li>"
    )
  return (
    '<div class="tc-card-box">'
    "<strong>表示モードの違い</strong><ul>"
    + "".join(items)
    + "</ul></div>"
  )


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
  from tech_cartography.runtime.demo_output_paths import (
    LEGACY_EVIDENCE_MAP_PATHS,
    resolve_bundle_or_legacy,
  )

  base_dir = _resolve_project_root(project_root)
  missing: list[str] = []
  errors: list[str] = []

  def _artifact_path(key: str, bundle_name: str) -> Path:
    return resolve_bundle_or_legacy(
      base_dir,
      bundle_name,
      LEGACY_EVIDENCE_MAP_PATHS[key],
      publication_number=publication_number,
    )

  md_path = _artifact_path("evidence_map_synthesis_md", "evidence_map_synthesis.md")
  json_path = _artifact_path("evidence_map_synthesis_json", "evidence_map_synthesis.json")
  items_path = _artifact_path("evidence_map_items_csv", "evidence_map_items.csv")
  papers_path = _artifact_path("selected_evidence_papers_csv", "selected_evidence_papers.csv")
  links_path = _artifact_path("claim_paper_candidate_links_csv", "claim_paper_candidate_links.csv")
  relevance_path = _artifact_path(
    "paper_candidate_relevance_report_md",
    "paper_candidate_relevance_report.md",
  )
  openalex_path = _artifact_path("openalex_execution_summary_md", "openalex_execution_summary.md")

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


def render_demo_mode_banner(artifacts: EvidenceMapDemoArtifacts) -> None:
  st.markdown(inject_easy_ui_css(), unsafe_allow_html=True)
  title = f"デモモード: {artifacts.publication_number} Evidence Map"
  st.markdown(
    render_info_box(
      f"{title}<br>"
      "このデモは既存outputsを読み込んで表示しています。新しいAPI実行は行っていません。"
      f"<br>status: {_format_status_label(artifacts.status)}"
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


def render_demo_story_cards(artifacts: EvidenceMapDemoArtifacts | None = None) -> str:
  status_label = translate_label(_format_status_label(artifacts.status)) if artifacts else "Evidence Map demo"
  card1 = (
    '<div class="tc-card-box">'
    "<strong>Tech Cartographyがやること</strong><ol>"
    "<li>特許候補を集める</li>"
    "<li>読むべき特許を選ぶ</li>"
    "<li>請求項から技術要素を抽出する</li>"
    "<li>論文候補と対応づける</li>"
    "<li>企業・市場シグナルとつなげる</li>"
    "<li>Evidence GapとNext Actionsを出す</li>"
    "</ol></div>"
  )
  card2 = (
    '<div class="tc-card-box">'
    "<strong>今回詳しく読む特許</strong><ul>"
    f"<li>公報番号: {DEMO_PUBLICATION_NUMBER}</li>"
    f"<li>取得ルート: {translate_label(ROUTE_LABEL)}</li>"
    f"<li>状態: {status_label}</li>"
    "<li>Manual Claims から請求項を読み、論文候補と対応づけた Evidence Map を表示しています</li>"
    "</ul></div>"
  )
  return card1 + card2 + render_where_to_look_card() + render_ui_mode_guide_card()


def render_evidence_map_summary(artifacts: EvidenceMapDemoArtifacts) -> None:
  st.subheader("Evidence Map Summary")
  metrics = build_evidence_map_summary_metrics(artifacts)
  st.markdown(render_metric_cards(metrics), unsafe_allow_html=True)
  st.markdown(render_evidence_map_reading_guide(), unsafe_allow_html=True)


def render_selected_evidence_papers(artifacts: EvidenceMapDemoArtifacts) -> None:
  st.subheader("Selected Evidence Papers")
  st.markdown(render_info_box(SELECTED_PAPERS_NOTICE), unsafe_allow_html=True)
  display_df = prepare_selected_papers_display_df(artifacts.selected_papers_df)
  if display_df.empty:
    st.warning("Selected Evidence Papers の成果物がまだありません。")
    return
  render_dataframe_stretch(display_df, hide_index=True)


def render_claim_paper_links(artifacts: EvidenceMapDemoArtifacts, *, developer_mode: bool = False) -> None:
  st.subheader("Claim × Paper Candidate Links")
  st.markdown(render_caution_box(CLAIM_LINKS_NOTICE), unsafe_allow_html=True)
  source_df = artifacts.claim_paper_links_df
  if not developer_mode:
    source_df = filter_claim_paper_link_rows(source_df)
  display_df = prepare_claim_paper_links_display_df(source_df)
  if display_df.empty:
    if not developer_mode and not artifacts.claim_paper_links_df.empty:
      st.info(CLAIM_ELEMENT_MISSING_GUIDANCE)
    else:
      st.warning("Claim × Paper Candidate Links の成果物がまだありません。")
    if developer_mode and not artifacts.claim_paper_links_df.empty:
      with st.expander("開発者向け: raw Claim × Paper links", expanded=False):
        render_dataframe_stretch(
          prepare_claim_paper_links_display_df(artifacts.claim_paper_links_df),
          hide_index=True,
        )
    return
  render_dataframe_stretch(display_df, hide_index=True)
  if developer_mode and not artifacts.claim_paper_links_df.empty:
    with st.expander("開発者向け: raw Claim × Paper links", expanded=False):
      render_dataframe_stretch(
        prepare_claim_paper_links_display_df(artifacts.claim_paper_links_df),
        hide_index=True,
      )


def render_evidence_gaps_section(artifacts: EvidenceMapDemoArtifacts) -> None:
  st.subheader("Evidence Gaps（確認が必要な点）")
  gaps = get_fixed_evidence_gaps(artifacts.evidence_map_json)
  gap_html = "".join(f"<li>{gap}</li>" for gap in gaps)
  st.markdown(
    render_warning_box(
      f"<ul>{gap_html}</ul>"
      "これらはデータ制約と未確認項目を示す注意事項です。"
    ),
    unsafe_allow_html=True,
  )


def render_next_actions_section(artifacts: EvidenceMapDemoArtifacts) -> None:
  st.subheader("Next Actions（次にやること）")
  actions = get_fixed_next_actions(artifacts.evidence_map_json)
  action_html = "".join(f"<li>{action}</li>" for action in actions)
  st.markdown(
    render_info_box(
      f"<ul>{action_html}</ul>"
      "研究者・審査員が、次に何をすればよいかを把握するための案内です。"
    ),
    unsafe_allow_html=True,
  )


def render_evidence_gaps_and_next_actions(artifacts: EvidenceMapDemoArtifacts) -> None:
  render_evidence_gaps_section(artifacts)
  render_next_actions_section(artifacts)
  if artifacts.evidence_map_md:
    with st.expander("Evidence Map Synthesis（Markdown抜粋）"):
      st.markdown(artifacts.evidence_map_md[:8000])


def render_evidence_map_report(artifacts: EvidenceMapDemoArtifacts) -> None:
  st.subheader("Evidence Map レポート")
  st.markdown(render_executive_summary(), unsafe_allow_html=True)
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


def render_demo_evidence_tab(artifacts: EvidenceMapDemoArtifacts, *, developer_mode: bool = False) -> None:
  st.caption("論文候補は技術背景の確認候補です。FTO・侵害・有効性判断ではありません。")
  render_evidence_map_summary(artifacts)
  render_selected_evidence_papers(artifacts)
  render_claim_paper_links(artifacts, developer_mode=developer_mode)
  render_evidence_gaps_and_next_actions(artifacts)
  if not artifacts.evidence_items_df.empty:
    with st.expander("Evidence Map Items"):
      render_dataframe_stretch(artifacts.evidence_items_df.head(50), hide_index=True)


def render_demo_start_tab(artifacts: EvidenceMapDemoArtifacts) -> None:
  st.markdown(render_demo_story_cards(artifacts), unsafe_allow_html=True)
  st.markdown(render_three_minute_demo_guide(), unsafe_allow_html=True)
  st.caption(
    f"デモ成果物: {artifacts.publication_number} / "
    f"状態: {translate_label(_format_status_label(artifacts.status))}"
  )
  from tech_cartography.ui.demo_safe_ui import render_usage_notices_expander

  render_usage_notices_expander(key="demo_start_usage_notices", expanded=False)
