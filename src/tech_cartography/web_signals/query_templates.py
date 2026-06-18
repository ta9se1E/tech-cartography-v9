"""Query templates for Tavily Web Signal search (Phase 23.1)."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field

TECHNOLOGY_TERMS: tuple[str, ...] = (
  "PAN carbon fiber",
  "polyacrylonitrile carbon fiber",
  "carbonization",
  "stabilization",
  "surface treatment",
  "sizing",
  "tensile strength",
  "modulus",
  "composite",
  "aerospace",
  "hydrogen tank",
  "pressure vessel",
)

CATEGORY_ALIASES: dict[str, str] = {
  "grant": "money",
  "funding": "money",
  "disclosure": "ir_disclosure",
  "market": "company",
}

NATIONAL_PROJECT_QUERIES_EN: tuple[str, ...] = (
  "PAN carbon fiber carbonization NEDO",
  "polyacrylonitrile carbon fiber METI project",
  "carbon fiber hydrogen tank NEDO grant",
  "carbon fiber composite JST project",
)

NATIONAL_PROJECT_QUERIES_JA: tuple[str, ...] = (
  "炭素繊維 NEDO 研究開発",
  "PAN系 炭素繊維 JST 研究課題",
  "炭素繊維 経済産業省 プロジェクト",
)

IR_DISCLOSURE_QUERIES_EN: tuple[str, ...] = (
  "carbon fiber investor relations capital investment",
  "carbon fiber earnings presentation expansion investment",
  "carbon fiber integrated report R&D investment",
)

IR_DISCLOSURE_QUERIES_JA: tuple[str, ...] = (
  "炭素繊維 IR 設備投資",
  "炭素繊維 決算説明資料 研究開発",
  "炭素繊維 統合報告書 研究開発",
  "炭素繊維 適時開示 設備投資",
)

COMPANY_QUERIES_EN: tuple[str, ...] = (
  "carbon fiber production capacity expansion company press release",
)

COMPANY_QUERIES_JA: tuple[str, ...] = (
  "炭素繊維 生産能力 増強 プレスリリース",
  "炭素繊維 量産 設備投資 ニュース",
)

LOCAL_NEWS_QUERIES_JA: tuple[str, ...] = (
  "炭素繊維 工場 増設 地元 ニュース",
  "炭素繊維 設備投資 地方紙",
  "複合材料 工場 新設 自治体",
)

HUMAN_QUERIES_EN: tuple[str, ...] = (
  "carbon fiber process engineer job carbonization",
  "PAN carbon fiber researcher carbonization",
)

HUMAN_QUERIES_JA: tuple[str, ...] = (
  "炭素繊維 炭化 エンジニア 求人",
  "炭素繊維 研究者 共同研究",
)

CATEGORY_DEFAULTS: dict[str, dict[str, list[str] | str]] = {
  "national_project": {
    "intended_signal_type": "national_project",
    "include_domains": ["jst.go.jp", "nedo.go.jp", "meti.go.jp", "grants.jst.go.jp", "kaken.nii.ac.jp"],
    "exclude_domains": [],
  },
  "money": {
    "intended_signal_type": "money",
    "include_domains": ["jst.go.jp", "nedo.go.jp", "meti.go.jp", "grants.jst.go.jp"],
    "exclude_domains": [],
  },
  "ir_disclosure": {
    "intended_signal_type": "ir_disclosure",
    "include_domains": ["edinet-fsa.go.jp", "disclosure2.edinet-fsa.go.jp", "jpx.co.jp"],
    "exclude_domains": [],
  },
  "company": {
    "intended_signal_type": "company",
    "include_domains": [],
    "exclude_domains": ["linkedin.com", "indeed.com", "wantedly.com"],
  },
  "local_news": {
    "intended_signal_type": "local_news",
    "include_domains": [],
    "exclude_domains": [],
  },
  "human": {
    "intended_signal_type": "human",
    "include_domains": [],
    "exclude_domains": ["linkedin.com", "facebook.com", "twitter.com"],
  },
}


@dataclass
class WebSignalQuery:
  query_id: str
  category: str
  query: str
  language: str
  intended_signal_type: str
  include_domains: list[str] = field(default_factory=list)
  exclude_domains: list[str] = field(default_factory=list)
  notes: str = ""

  def to_dict(self) -> dict[str, object]:
    return asdict(self)


def _new_query_id() -> str:
  return f"wsq-{uuid.uuid4().hex[:8]}"


def _queries_for_category(category: str, language: str, topic: str) -> list[str]:
  cat = CATEGORY_ALIASES.get(category, category)
  if cat == "national_project" or cat == "money":
    return list(NATIONAL_PROJECT_QUERIES_EN if language == "en" else NATIONAL_PROJECT_QUERIES_JA)
  if cat == "ir_disclosure":
    return list(IR_DISCLOSURE_QUERIES_EN if language == "en" else IR_DISCLOSURE_QUERIES_JA)
  if cat == "company":
    return list(COMPANY_QUERIES_EN if language == "en" else COMPANY_QUERIES_JA)
  if cat == "local_news":
    return list(LOCAL_NEWS_QUERIES_JA if language == "ja" else ())
  if cat == "human":
    return list(HUMAN_QUERIES_EN if language == "en" else HUMAN_QUERIES_JA)
  return [topic] if topic else []


def build_web_signal_queries(
  topic: str,
  categories: list[str],
  languages: list[str] | None = None,
) -> list[WebSignalQuery]:
  langs = languages or ["ja", "en"]
  queries: list[WebSignalQuery] = []
  seen: set[str] = set()

  for category in categories:
    normalized = CATEGORY_ALIASES.get(category, category)
    defaults = CATEGORY_DEFAULTS.get(normalized, {
      "intended_signal_type": normalized,
      "include_domains": [],
      "exclude_domains": [],
    })
    for language in langs:
      for query_text in _queries_for_category(normalized, language, topic):
        key = f"{normalized}|{language}|{query_text}"
        if key in seen:
          continue
        seen.add(key)
        queries.append(
          WebSignalQuery(
            query_id=_new_query_id(),
            category=normalized,
            query=query_text,
            language=language,
            intended_signal_type=str(defaults["intended_signal_type"]),
            include_domains=list(defaults.get("include_domains") or []),
            exclude_domains=list(defaults.get("exclude_domains") or []),
            notes=f"topic={topic}",
          ),
        )
  return queries
