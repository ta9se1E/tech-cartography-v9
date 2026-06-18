"""Classify Tavily results into Web Signal types (Phase 23.1)."""

from __future__ import annotations

import re

from tech_cartography.web_signals.schema import DISCLOSURE_TYPES, extract_source_domain

IR_TITLE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
  re.compile(pattern, re.IGNORECASE)
  for pattern in (
    r"\bIR\b",
    r"investor relations",
    r"integrated report",
    r"annual report",
    r"earnings",
    r"financial results",
    r"securities report",
    r"timely disclosure",
    r"決算",
    r"決算説明",
    r"統合報告書",
    r"有価証券報告書",
    r"適時開示",
    r"投資家向け",
  )
)

DISCLOSURE_TYPE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
  ("financial_results", re.compile(r"financial results|決算短信|業績", re.IGNORECASE)),
  ("earnings_presentation", re.compile(r"earnings presentation|決算説明", re.IGNORECASE)),
  ("integrated_report", re.compile(r"integrated report|統合報告書", re.IGNORECASE)),
  ("annual_report", re.compile(r"annual report|有価証券報告書", re.IGNORECASE)),
  ("securities_report", re.compile(r"securities report|有価証券", re.IGNORECASE)),
  ("timely_disclosure", re.compile(r"timely disclosure|適時開示|TDnet", re.IGNORECASE)),
  ("press_release", re.compile(r"press release|プレスリリース|news release", re.IGNORECASE)),
  ("grant_notice", re.compile(r"grant|公募|補助金|研究費", re.IGNORECASE)),
  ("project_page", re.compile(r"project|研究課題|プロジェクト", re.IGNORECASE)),
)

DISCLOSURE_PLATFORM_DOMAINS: frozenset[str] = frozenset(
  {
    "fsa.go.jp",
    "edinet-fsa.go.jp",
    "disclosure2.edinet-fsa.go.jp",
    "jpx.co.jp",
  },
)

IR_PATH_HINTS: tuple[str, ...] = (
  "/ir/",
  "/investor",
  "/investors/",
  "/ir-library",
  "/english/ir/",
)


def infer_disclosure_type(title: str, snippet: str = "") -> str:
  text = f"{title} {snippet}".strip()
  for label, pattern in DISCLOSURE_TYPE_PATTERNS:
    if pattern.search(text):
      return label
  return "unknown"


def looks_like_ir_disclosure(title: str, snippet: str, source_url: str) -> bool:
  text = f"{title} {snippet}".strip()
  if any(pattern.search(text) for pattern in IR_TITLE_PATTERNS):
    return True
  domain = extract_source_domain(source_url)
  if domain in DISCLOSURE_PLATFORM_DOMAINS:
    return True
  lower_url = str(source_url or "").lower()
  if any(hint in lower_url for hint in IR_PATH_HINTS):
    return True
  return False


def classify_signal_type(
  *,
  title: str,
  snippet: str,
  source_url: str,
  default_signal_type: str,
  query_category: str = "",
) -> str:
  domain = extract_source_domain(source_url)
  if domain in DISCLOSURE_PLATFORM_DOMAINS or looks_like_ir_disclosure(title, snippet, source_url):
    if query_category in {"ir_disclosure", "disclosure"}:
      return "ir_disclosure"
    if any(k in f"{title} {snippet}".lower() for k in ("grant", "公募", "補助金", "nedo", "jst")):
      return default_signal_type if default_signal_type != "other" else "grant"
    return "ir_disclosure"

  text = f"{title} {snippet}".lower()
  category = str(query_category or "").lower()

  if category in {"national_project", "money", "grant", "funding"}:
    if any(k in text for k in ("grant", "公募", "補助金", "研究費", "project", "nedo", "jst")):
      if "equipment" in text or "設備投資" in text:
        return "equipment_investment"
      if "grant" in text or "公募" in text or "補助金" in text:
        return "grant"
      return category if category in {"national_project", "money"} else "national_project"

  if category == "human" or any(k in text for k in ("job", "求人", "researcher", "engineer")):
    return "human"

  if category == "local_news":
    return "local_news"

  if category in {"company", "market"}:
    return "company" if category == "company" else "market"

  if default_signal_type and default_signal_type != "other":
    return default_signal_type
  return "other"


def infer_disclosure_type_safe(title: str, snippet: str = "") -> str:
  value = infer_disclosure_type(title, snippet)
  return value if value in DISCLOSURE_TYPES else "unknown"
