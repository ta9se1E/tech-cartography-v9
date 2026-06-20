"""Centralized Japanese label rendering for demo UI (Phase 24.5B)."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

# Canonical demo-facing Evidence Gaps / Next Actions (Phase 24.5B)
POLISHED_EVIDENCE_GAPS: tuple[str, ...] = (
  "明細書・実施例が未確認",
  "数値条件・測定条件が未抽出",
  "欠陥と物性低下の直接関係が未確認",
  "論文候補は技術背景の裏取り候補であり、特許主張の証明ではない",
  "Webシグナルと対象特許の直接関係は未確認",
  "公的プロジェクト・IR・企業ニュースは原典確認が必要",
)

POLISHED_NEXT_ACTIONS: tuple[str, ...] = (
  "Google Patents / J-PlatPat で明細書と実施例を確認する",
  "Claim Element ごとに、明細書中の実施例・数値条件を抜き出す",
  "Selected Evidence Papers 上位3件を技術者が読む",
  "Webシグナルの原典URLを開き、対象技術が同じ範囲か確認する",
  "特許・論文・Webシグナルの関係を専門家がレビューする",
)

LABEL_MAP: dict[str, str] = {
  "claims_only": "請求項のみで判定",
  "weak-to-medium": "裏取り強度: 弱〜中",
  "weak_to_medium": "裏取り強度: 弱〜中",
  "low_fulltext_evidence": "明細書未確認のため限定的",
  "supporting evidence candidate": "技術背景の確認候補",
  "supporting_evidence_candidate": "技術背景の確認候補",
  "signal candidate": "確認候補",
  "national_project": "国家プロジェクト候補",
  "money": "公的予算・資金関連候補",
  "ir_disclosure": "IR・開示候補",
  "blocked_missing_paper_or_web_signal": "論文またはWeb候補が不足",
  "query_plan_ready": "検索計画作成済み",
  "actual_data": "実データ取得済み",
  "property_background": "物性・背景文献候補",
  "strong_material_process_background": "材料・プロセス背景候補",
  "surface_interface_background": "界面・表面背景候補",
  "material_process_background": "材料・プロセス背景",
  "material_process_supporting_evidence": "材料・プロセス裏取り候補",
  "property_supporting_evidence": "物性裏取り候補",
  "low": "低",
  "medium": "中",
  "high": "高",
  "Manual Claims Route": "Manual Claims ルート",
  "Evidence Map ready": "Evidence Map 準備完了",
  "Evidence Map partial": "Evidence Map 一部のみ",
  "Evidence Map missing": "Evidence Map 未生成",
  "Evidence Map error": "Evidence Map 読み込みエラー",
}

SIGNAL_TYPE_LABELS: dict[str, str] = {
  "national_project": "国家プロジェクト候補",
  "money": "公的予算・資金関連候補",
  "ir_disclosure": "IR・開示候補",
  "company_news": "企業ニュース候補",
  "local_news": "地域ニュース候補",
  "research_project": "研究プロジェクト候補",
}


def translate_label(value: Any, *, default: str | None = None) -> str:
  """Translate a technical token to Japanese; pass through unknown values."""
  if value is None:
    return default or "—"
  text = str(value).strip()
  if not text:
    return default or "—"
  if text in LABEL_MAP:
    return LABEL_MAP[text]
  lowered = text.lower()
  if lowered in LABEL_MAP:
    return LABEL_MAP[lowered]
  if lowered in SIGNAL_TYPE_LABELS:
    return SIGNAL_TYPE_LABELS[lowered]
  if "supporting_evidence" in lowered or "supporting evidence" in lowered:
    return "技術背景の確認候補"
  if "signal candidate" in lowered:
    return "確認候補"
  if "claims_only" in lowered and "weak" in lowered:
    return "請求項のみで判定 / 裏取り強度: 弱〜中"
  return default if default is not None else text


def normalize_doi(doi: Any) -> str:
  if doi is None:
    return ""
  text = str(doi).strip()
  if not text or text.lower() in {"n/a", "none", "not available", "nan"}:
    return ""
  if text.startswith("https://doi.org/"):
    return text.removeprefix("https://doi.org/").strip()
  if text.startswith("http://doi.org/"):
    return text.removeprefix("http://doi.org/").strip()
  if text.lower().startswith("doi:"):
    return text[4:].strip()
  return text


def resolve_paper_url(row: dict[str, Any]) -> str:
  """Resolve best paper URL from doi, landing_page_url, source_url, openalex_id, url."""
  doi = normalize_doi(row.get("doi") or row.get("paper_doi"))
  if doi:
    return f"https://doi.org/{quote(doi, safe='/-:._')}"

  for key in ("landing_page_url", "source_url", "url"):
    raw = str(row.get(key) or "").strip()
    if raw.startswith("http://") or raw.startswith("https://"):
      return raw

  openalex_id = str(row.get("openalex_id") or row.get("paper_id") or "").strip()
  if openalex_id:
    if openalex_id.startswith("http"):
      return openalex_id
    oid = openalex_id.rstrip("/").split("/")[-1]
    if oid.startswith("W"):
      return f"https://openalex.org/{oid}"
  return ""


def format_paper_link_markdown(url: str, *, label: str = "論文を開く") -> str:
  if not url:
    return "—"
  return f"[{label}]({url})"


def format_paper_link_html(url: str, *, label: str = "論文を開く") -> str:
  if not url:
    return "—"
  safe_url = url.replace('"', "%22")
  return f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">{label}</a>'


def why_review_signal(row: dict[str, Any]) -> str:
  """Short Japanese reason why a web signal is worth reviewing."""
  signal_type = translate_label(row.get("signal_type"), default="確認候補")
  domain = str(row.get("source_domain") or row.get("source_category") or "").strip()
  project = str(row.get("related_project") or row.get("related_technology_terms") or "").strip()
  parts = [f"{signal_type}として確認"]
  if domain:
    parts.append(f"出典: {domain}")
  if project:
    parts.append(f"関連: {_truncate(project, 60)}")
  return " / ".join(parts)


def next_signal_verification(row: dict[str, Any]) -> str:
  action = str(row.get("next_verification_action") or "").strip()
  if action:
    return _truncate(action, 120)
  return "原典URLを開き、対象技術の範囲が一致するか確認する"


def _truncate(text: str, max_len: int) -> str:
  if len(text) <= max_len:
    return text
  return text[: max_len - 1] + "…"
