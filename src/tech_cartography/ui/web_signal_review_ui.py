"""Web Signal Review Pack UI — load review_pack outputs and render Streamlit sections (Phase 23.3)."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.reports.project_export import load_records_csv
from tech_cartography.ui.easy_japanese_ui import (
  render_caution_box,
  render_dataframe_stretch,
  render_info_box,
  render_metric_cards,
  render_warning_box,
)

NOT_AVAILABLE = "not available"
WEB_SIGNALS_RELATIVE_DIR = "outputs/web_signals"
DEFAULT_BATCH_DIR = "tavily_pan_carbon_fiber"

ARTIFACT_FILES: dict[str, str] = {
  "review_pack_json": "web_signal_review_pack.json",
  "review_items_csv": "web_signal_review_items.csv",
  "high_priority_csv": "high_priority_web_signals.csv",
  "ir_disclosure_csv": "ir_disclosure_candidates.csv",
  "money_national_project_csv": "money_national_project_candidates.csv",
  "company_local_news_csv": "company_local_news_candidates.csv",
  "rejected_csv": "rejected_or_low_quality_sources.csv",
  "summary_md": "web_signal_review_summary.md",
}

WEB_SIGNAL_CAUTION_EN = (
  "Web signals are signal candidates, not final conclusions. "
  "NEDO / JST / METI などの公的ソースであっても、対象特許・論文との関係はまだ人間が確認する必要があります。 "
  "IR / disclosure signals require document-level verification. "
  "Human signals require careful identity verification. "
  "Money / national_project signals require source verification. "
  "Synthetic demo signal must be clearly labeled. "
  "This is not FTO, infringement, or validity analysis."
)

WEB_SIGNAL_CAUTION_JA = (
  "Webシグナルは最終結論ではなく、確認候補です。"
  "公的機関・企業IR・ニュース等の情報は、特許や論文との関係を人間が確認する必要があります。"
  "FTO、侵害、有効性判断ではありません。"
)

HIGH_PRIORITY_INTRO = (
  "高優先度Webシグナルは、Evidence Mapへ接続する前のレビュー候補です。"
  "この段階では、特許・論文との関係を断定しません。"
)

MONEY_NATIONAL_INTRO = (
  "これは公的研究開発・国家プロジェクト・資金関連の候補シグナルです。"
  "金額やプロジェクト規模は、元資料を確認するまでは断定しません。"
)

IR_EMPTY_INFO = (
  "今回のWeb Signal Review Packでは、IR / disclosure candidates はまだ見つかっていません。"
  "次Phaseで、企業公式IRページ、EDINET、JPX/TDnet、統合報告書、決算説明資料に対象を広げる予定です。"
)

COMPANY_LOCAL_EMPTY_INFO = (
  "今回のWeb Signal Review Packでは、company / local news candidates はまだ見つかっていません。"
  "企業プレスリリースや地方紙・自治体ニュースの候補は次Phaseで拡張予定です。"
)

REJECTED_EXPANDER_TITLE = "Rejected / Low Quality Sources（確認用）"
REJECTED_EXPANDER_HELP = (
  "この一覧は、source qualityが低い、内容が薄い、URLがない、"
  "Evidence Mapに入れるには不十分と判定された候補です。"
  "削除ではなく、監査性のために保存しています。"
)

NEXT_PHASE_CARD_TITLE = "次の接続先"
NEXT_PHASE_CARD_BODY = (
  "次Phaseでは、Claim Element / Selected Evidence Papers / Web Signal の技術語を照合し、"
  "Patent × Paper × Web Signal Link Candidate を作ります。"
  "ただし、リンクは断定ではなく、technology_theme_match / source_overlap / "
  "project_context_match などの候補として扱います。"
)

MISSING_ARTIFACT_WARNING = (
  "Web Signal Review Pack の成果物が一部見つかりません。"
  "先に scripts/run_tavily_web_signal_search.py --build-review-pack を実行してください。"
)

HIGH_PRIORITY_COLUMNS: tuple[str, ...] = (
  "signal_id",
  "review_priority",
  "signal_type",
  "source_title",
  "source_domain",
  "source_quality",
  "source_category",
  "disclosure_type",
  "evidence_sentences",
  "confidence",
  "verification_status",
  "next_verification_action",
  "source_url",
)

MONEY_NATIONAL_COLUMNS: tuple[str, ...] = (
  "signal_id",
  "review_priority",
  "signal_type",
  "source_title",
  "source_domain",
  "source_quality",
  "evidence_sentences",
  "related_project",
  "related_institution",
  "related_technology_terms",
  "confidence",
  "verification_status",
  "next_verification_action",
  "source_url",
)

IR_DISCLOSURE_COLUMNS: tuple[str, ...] = (
  "signal_id",
  "review_priority",
  "signal_type",
  "disclosure_type",
  "source_title",
  "source_domain",
  "source_quality",
  "fiscal_period",
  "document_date",
  "related_company",
  "evidence_sentences",
  "confidence",
  "verification_status",
  "next_verification_action",
  "source_url",
)

COMPANY_LOCAL_COLUMNS: tuple[str, ...] = (
  "signal_id",
  "review_priority",
  "signal_type",
  "source_title",
  "source_domain",
  "source_quality",
  "evidence_sentences",
  "related_company",
  "related_institution",
  "confidence",
  "verification_status",
  "next_verification_action",
  "source_url",
)


@dataclass
class WebSignalReviewUIArtifacts:
  status: str
  base_dir: Path
  review_pack_dir: Path
  review_pack_json_path: Path | None
  review_items_df: pd.DataFrame
  high_priority_df: pd.DataFrame
  ir_disclosure_df: pd.DataFrame
  money_national_project_df: pd.DataFrame
  company_local_news_df: pd.DataFrame
  rejected_df: pd.DataFrame
  summary_md: str | None
  missing_artifacts: list[str] = field(default_factory=list)
  errors: list[str] = field(default_factory=list)


def get_web_signal_caution_text() -> tuple[str, str]:
  return WEB_SIGNAL_CAUTION_EN, WEB_SIGNAL_CAUTION_JA


def safe_read_text(path: Path) -> tuple[str | None, str]:
  if not path.exists():
    return None, f"file not found: {path}"
  try:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
      return None, f"empty file: {path}"
    return text, ""
  except OSError as exc:
    return None, f"read error ({path.name}): {exc}"


def safe_read_csv(path: Path) -> tuple[pd.DataFrame, str]:
  if not path.exists():
    return pd.DataFrame(), f"file not found: {path}"
  try:
    rows = load_records_csv(str(path))
    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    return _normalize_dataframe(df), ""
  except Exception as exc:  # noqa: BLE001
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


def _format_display_value(value: Any, *, default: str = NOT_AVAILABLE) -> str:
  if _is_empty_value(value):
    return default
  return str(value).strip()


def _truncate_text(value: Any, max_len: int) -> str:
  text = _format_display_value(value, default="")
  if text == NOT_AVAILABLE or not text:
    return NOT_AVAILABLE
  if len(text) <= max_len:
    return text
  return text[: max_len - 1] + "…"


def _parse_evidence_sentences(value: Any) -> list[str]:
  if _is_empty_value(value):
    return []
  if isinstance(value, list):
    return [str(item).strip() for item in value if str(item).strip()]
  text = str(value).strip()
  if text.startswith("[") and text.endswith("]"):
    try:
      parsed = ast.literal_eval(text)
      if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    except (SyntaxError, ValueError):
      pass
  parts = [part.strip() for part in re.split(r"[;|]\s*", text) if part.strip()]
  return parts if parts else ([text] if text else [])


def _format_evidence_sentences(value: Any, *, max_len: int = 180) -> str:
  sentences = _parse_evidence_sentences(value)
  if not sentences:
    return NOT_AVAILABLE
  joined = " | ".join(sentences)
  return _truncate_text(joined, max_len)


def _format_source_url_link(source_url: Any, source_title: Any = "") -> str:
  url = str(source_url or "").strip()
  if not url:
    return NOT_AVAILABLE
  title = _truncate_text(source_title or url, 80)
  if title == NOT_AVAILABLE:
    title = url
  return f"[{title}]({url})"


def _coerce_numeric_priority(value: Any) -> float:
  if _is_empty_value(value):
    return -1.0
  try:
    return float(value)
  except (TypeError, ValueError):
    return -1.0


def _select_display_columns(df: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
  if df is None or df.empty:
    return pd.DataFrame(columns=list(columns))

  rows: list[dict[str, str]] = []
  for _, row in df.iterrows():
    row_dict = {str(k): _normalize_cell(v) for k, v in row.to_dict().items()}
    display_row: dict[str, str] = {}
    for col in columns:
      if col == "source_url":
        display_row[col] = _format_source_url_link(row_dict.get("source_url"), row_dict.get("source_title"))
      elif col == "evidence_sentences":
        display_row[col] = _format_evidence_sentences(row_dict.get("evidence_sentences"))
      elif col == "source_title":
        display_row[col] = _truncate_text(row_dict.get("source_title"), 120)
      elif col in row_dict:
        display_row[col] = _format_display_value(row_dict[col])
      else:
        display_row[col] = NOT_AVAILABLE
    rows.append(display_row)
  return pd.DataFrame(rows, columns=list(columns))


def prepare_web_signal_display_df(
  df: pd.DataFrame | None,
  columns: tuple[str, ...] | None = None,
) -> pd.DataFrame:
  if df is None or df.empty:
    target_cols = list(columns or HIGH_PRIORITY_COLUMNS)
    return pd.DataFrame(columns=target_cols)

  working = _normalize_dataframe(df.copy())
  if "review_priority" in working.columns:
    working["_priority_sort"] = working["review_priority"].apply(_coerce_numeric_priority)
    working = working.sort_values("_priority_sort", ascending=False).drop(columns=["_priority_sort"])

  display_cols = columns or HIGH_PRIORITY_COLUMNS
  return _select_display_columns(working, display_cols)


def get_web_signal_status_counts(
  *,
  review_items_df: pd.DataFrame | None = None,
  high_priority_df: pd.DataFrame | None = None,
  ir_disclosure_df: pd.DataFrame | None = None,
  money_national_project_df: pd.DataFrame | None = None,
  company_local_news_df: pd.DataFrame | None = None,
  rejected_df: pd.DataFrame | None = None,
) -> dict[str, int]:
  def _count(frame: pd.DataFrame | None) -> int:
    if frame is None or frame.empty:
      return 0
    return int(len(frame))

  return {
    "total_review_signals": _count(review_items_df),
    "high_priority_signals": _count(high_priority_df),
    "money_national_project_signals": _count(money_national_project_df),
    "ir_disclosure_signals": _count(ir_disclosure_df),
    "company_local_news_signals": _count(company_local_news_df),
    "rejected_low_quality_sources": _count(rejected_df),
  }


def _resolve_review_pack_dir(project_root: Path, batch_dir: str | None) -> Path:
  signals_root = project_root / WEB_SIGNALS_RELATIVE_DIR
  if batch_dir:
    return signals_root / batch_dir / "review_pack"

  preferred = signals_root / DEFAULT_BATCH_DIR / "review_pack"
  if preferred.exists():
    return preferred

  candidates: list[Path] = []
  if signals_root.exists():
    for child in signals_root.iterdir():
      if not child.is_dir():
        continue
      review_pack = child / "review_pack"
      if review_pack.is_dir():
        candidates.append(review_pack)

  if not candidates:
    return preferred
  return max(candidates, key=lambda path: path.stat().st_mtime)


def _compute_loader_status(
  *,
  missing: list[str],
  errors: list[str],
  has_review_data: bool,
) -> str:
  if errors and not has_review_data:
    return "error"
  if not missing and not errors:
    return "ready"
  if len(missing) >= len(ARTIFACT_FILES):
    return "missing"
  if has_review_data:
    return "partial"
  if errors:
    return "error"
  return "missing"


def load_web_signal_review_artifacts(
  project_root: Path | str = ".",
  batch_dir: str | None = None,
) -> WebSignalReviewUIArtifacts:
  base_dir = Path(project_root).resolve()
  review_pack_dir = _resolve_review_pack_dir(base_dir, batch_dir)
  missing: list[str] = []
  errors: list[str] = []

  paths = {key: review_pack_dir / filename for key, filename in ARTIFACT_FILES.items()}

  review_items_df, items_err = safe_read_csv(paths["review_items_csv"])
  if items_err:
    if "not found" in items_err:
      missing.append("review_items_csv")
    else:
      errors.append(items_err)

  high_priority_df, high_err = safe_read_csv(paths["high_priority_csv"])
  if high_err:
    if "not found" in high_err:
      missing.append("high_priority_csv")
    else:
      errors.append(high_err)

  ir_disclosure_df, ir_err = safe_read_csv(paths["ir_disclosure_csv"])
  if ir_err:
    if "not found" in ir_err:
      missing.append("ir_disclosure_csv")
    else:
      errors.append(ir_err)

  money_national_project_df, money_err = safe_read_csv(paths["money_national_project_csv"])
  if money_err:
    if "not found" in money_err:
      missing.append("money_national_project_csv")
    else:
      errors.append(money_err)

  company_local_news_df, company_err = safe_read_csv(paths["company_local_news_csv"])
  if company_err:
    if "not found" in company_err:
      missing.append("company_local_news_csv")
    else:
      errors.append(company_err)

  rejected_df, rejected_err = safe_read_csv(paths["rejected_csv"])
  if rejected_err:
    if "not found" in rejected_err:
      missing.append("rejected_csv")
    else:
      errors.append(rejected_err)

  summary_md, summary_err = safe_read_text(paths["summary_md"])
  if summary_err:
    if "not found" in summary_err:
      missing.append("summary_md")
    else:
      errors.append(summary_err)

  review_pack_json_path = paths["review_pack_json"] if paths["review_pack_json"].exists() else None
  if review_pack_json_path is None:
    missing.append("review_pack_json")

  has_review_data = any(
    not frame.empty
    for frame in (
      review_items_df,
      high_priority_df,
      ir_disclosure_df,
      money_national_project_df,
      company_local_news_df,
    )
  )

  status = _compute_loader_status(missing=missing, errors=errors, has_review_data=has_review_data)

  return WebSignalReviewUIArtifacts(
    status=status,
    base_dir=base_dir,
    review_pack_dir=review_pack_dir,
    review_pack_json_path=review_pack_json_path,
    review_items_df=review_items_df,
    high_priority_df=high_priority_df,
    ir_disclosure_df=ir_disclosure_df,
    money_national_project_df=money_national_project_df,
    company_local_news_df=company_local_news_df,
    rejected_df=rejected_df,
    summary_md=summary_md,
    missing_artifacts=missing,
    errors=errors,
  )


def is_ir_disclosure_empty(artifacts: WebSignalReviewUIArtifacts) -> bool:
  return artifacts.ir_disclosure_df.empty


def is_company_local_news_empty(artifacts: WebSignalReviewUIArtifacts) -> bool:
  return artifacts.company_local_news_df.empty


def render_web_signal_caution_cards() -> None:
  caution_en, caution_ja = get_web_signal_caution_text()
  st.markdown(render_caution_box(f"{caution_en}<br><br>{caution_ja}"), unsafe_allow_html=True)


def render_web_signal_summary_cards(artifacts: WebSignalReviewUIArtifacts) -> None:
  counts = get_web_signal_status_counts(
    review_items_df=artifacts.review_items_df,
    high_priority_df=artifacts.high_priority_df,
    ir_disclosure_df=artifacts.ir_disclosure_df,
    money_national_project_df=artifacts.money_national_project_df,
    company_local_news_df=artifacts.company_local_news_df,
    rejected_df=artifacts.rejected_df,
  )
  metrics = [
    {"label": "Total Review Signals", "value": str(counts["total_review_signals"])},
    {"label": "High Priority Signals", "value": str(counts["high_priority_signals"])},
    {"label": "Money / National Project Signals", "value": str(counts["money_national_project_signals"])},
    {"label": "IR / Disclosure Signals", "value": str(counts["ir_disclosure_signals"])},
    {"label": "Company / Local News Signals", "value": str(counts["company_local_news_signals"])},
    {"label": "Rejected / Low Quality Sources", "value": str(counts["rejected_low_quality_sources"])},
  ]
  st.markdown(render_metric_cards(metrics), unsafe_allow_html=True)


def _render_signal_table(df: pd.DataFrame, columns: tuple[str, ...]) -> None:
  display_df = prepare_web_signal_display_df(df, columns)
  if display_df.empty:
    st.info("表示できるシグナル候補はありません。")
    return
  render_dataframe_stretch(display_df, hide_index=True)


def render_high_priority_web_signals(artifacts: WebSignalReviewUIArtifacts) -> None:
  st.subheader("High Priority Web Signals")
  st.markdown(render_info_box(HIGH_PRIORITY_INTRO), unsafe_allow_html=True)
  _render_signal_table(artifacts.high_priority_df, HIGH_PRIORITY_COLUMNS)


def render_money_national_project_candidates(artifacts: WebSignalReviewUIArtifacts) -> None:
  st.subheader("Money / National Project Candidates")
  st.markdown(render_info_box(MONEY_NATIONAL_INTRO), unsafe_allow_html=True)
  _render_signal_table(artifacts.money_national_project_df, MONEY_NATIONAL_COLUMNS)


def render_ir_disclosure_candidates(artifacts: WebSignalReviewUIArtifacts) -> None:
  st.subheader("IR / Disclosure Candidates")
  if is_ir_disclosure_empty(artifacts):
    st.info(IR_EMPTY_INFO)
    return
  _render_signal_table(artifacts.ir_disclosure_df, IR_DISCLOSURE_COLUMNS)


def render_company_local_news_candidates(artifacts: WebSignalReviewUIArtifacts) -> None:
  st.subheader("Company / Local News Candidates")
  if is_company_local_news_empty(artifacts):
    st.info(COMPANY_LOCAL_EMPTY_INFO)
    return
  _render_signal_table(artifacts.company_local_news_df, COMPANY_LOCAL_COLUMNS)


def render_rejected_low_quality_sources(artifacts: WebSignalReviewUIArtifacts) -> None:
  with st.expander(REJECTED_EXPANDER_TITLE, expanded=False):
    st.caption(REJECTED_EXPANDER_HELP)
    if artifacts.rejected_df.empty:
      st.info("rejected / low quality sources は 0 件です。")
      return
    display_df = prepare_web_signal_display_df(artifacts.rejected_df, HIGH_PRIORITY_COLUMNS)
    render_dataframe_stretch(display_df, hide_index=True)


def render_next_phase_card() -> None:
  st.markdown(
    render_info_box(f"<strong>{NEXT_PHASE_CARD_TITLE}</strong><br>{NEXT_PHASE_CARD_BODY}"),
    unsafe_allow_html=True,
  )


def render_web_signal_review_report(artifacts: WebSignalReviewUIArtifacts) -> None:
  with st.expander("Web Signal Review Summary", expanded=False):
    if artifacts.summary_md:
      st.markdown(artifacts.summary_md)
    else:
      st.info("web_signal_review_summary.md は not available です。")


def render_web_signal_review_section(artifacts: WebSignalReviewUIArtifacts) -> None:
  st.subheader("Web Signal Review Pack")
  render_web_signal_caution_cards()

  if artifacts.missing_artifacts:
    st.markdown(
      render_warning_box(
        f"{MISSING_ARTIFACT_WARNING}<br>missing: {', '.join(artifacts.missing_artifacts)}"
      ),
      unsafe_allow_html=True,
    )
  if artifacts.errors:
    with st.expander("読み込みエラー（デバッグ）"):
      for err in artifacts.errors:
        st.caption(err)

  if artifacts.status == "missing" and artifacts.review_items_df.empty and artifacts.high_priority_df.empty:
    st.info(
      "Review Pack 成果物が見つかりません。"
      "先に Tavily search + --build-review-pack を実行してください。"
    )
    render_next_phase_card()
    return

  st.caption(f"review_pack dir: {artifacts.review_pack_dir}")
  render_web_signal_summary_cards(artifacts)
  render_high_priority_web_signals(artifacts)
  render_money_national_project_candidates(artifacts)
  render_ir_disclosure_candidates(artifacts)
  render_company_local_news_candidates(artifacts)
  render_rejected_low_quality_sources(artifacts)
  render_web_signal_review_report(artifacts)
  render_next_phase_card()
