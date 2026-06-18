"""Source quality classification for Web Signals (Phase 23.0 / 23.1)."""

from __future__ import annotations

from tech_cartography.web_signals.schema import extract_source_domain

HIGH_QUALITY_DOMAINS: frozenset[str] = frozenset(
  {
    "jst.go.jp",
    "nedo.go.jp",
    "meti.go.jp",
    "mext.go.jp",
    "grants.jst.go.jp",
    "kaken.nii.ac.jp",
    "amed.go.jp",
    "fsa.go.jp",
    "edinet-fsa.go.jp",
    "disclosure2.edinet-fsa.go.jp",
    "jpx.co.jp",
  },
)

DISCLOSURE_PLATFORM_DOMAINS: frozenset[str] = frozenset(
  {
    "fsa.go.jp",
    "edinet-fsa.go.jp",
    "disclosure2.edinet-fsa.go.jp",
    "jpx.co.jp",
  },
)

PUBLIC_FUNDING_DOMAINS: frozenset[str] = frozenset(
  {
    "jst.go.jp",
    "nedo.go.jp",
    "grants.jst.go.jp",
    "kaken.nii.ac.jp",
    "amed.go.jp",
  },
)

NATIONAL_PROJECT_DOMAINS: frozenset[str] = frozenset(
  {
    "jst.go.jp",
    "nedo.go.jp",
    "meti.go.jp",
    "mext.go.jp",
    "grants.jst.go.jp",
    "kaken.nii.ac.jp",
    "amed.go.jp",
  },
)

GOVERNMENT_DOMAINS: frozenset[str] = frozenset(
  {
    "meti.go.jp",
    "mext.go.jp",
    "go.jp",
  },
)

LOW_QUALITY_HINTS: tuple[str, ...] = (
  "linkedin.com",
  "twitter.com",
  "x.com",
  "facebook.com",
  "instagram.com",
  "tiktok.com",
  "reddit.com",
  "medium.com",
  "note.com",
  "qiita.com",
  "wantedly.com",
  "indeed.com",
  "rikunabi.com",
  "mynavi.jp",
  "blogspot.",
  "wordpress.com",
)

JOB_BOARD_HINTS: tuple[str, ...] = (
  "indeed",
  "rikunabi",
  "mynavi",
  "wantedly",
  "doda",
  "en-japan",
)

INDUSTRY_MEDIA_HINTS: tuple[str, ...] = (
  "nikkei.com",
  "chemicaldaily.co.jp",
  "plasticsnews.com",
  "compositesworld.com",
)

LOCAL_NEWS_HINTS: tuple[str, ...] = (
  "local",
  "pref.",
  "city.",
  "news.co.jp",
  "shimbun",
)

LOCAL_GOVERNMENT_HINTS: tuple[str, ...] = (
  "pref.",
  "city.",
  "lg.jp",
  "go.jp",
)

IR_PATH_HINTS: tuple[str, ...] = (
  "/ir/",
  "/investor",
  "/investors/",
  "/ir-library",
  "/english/ir/",
)


def _match_domain(domain: str, suffix: str) -> bool:
  return domain == suffix or domain.endswith(f".{suffix}")


def _looks_like_ir_official(source_url: str, domain: str) -> bool:
  lower_url = str(source_url or "").lower()
  if any(hint in lower_url for hint in IR_PATH_HINTS):
    return True
  if domain.endswith(".co.jp") or domain.endswith(".com"):
    if any(part in lower_url for part in ("/ir/", "/investor", "investor-relations")):
      return True
  return False


def classify_source_quality(source_url: str, *, title: str = "", snippet: str = "") -> dict[str, str]:
  domain = extract_source_domain(source_url)
  if not domain:
    return {
      "source_domain": "",
      "source_quality": "unknown",
      "source_category": "search_result",
      "caveat": "source_url is missing; treat as unverified signal candidate.",
    }

  if domain in DISCLOSURE_PLATFORM_DOMAINS or any(
    _match_domain(domain, item) for item in DISCLOSURE_PLATFORM_DOMAINS
  ):
    return {
      "source_domain": domain,
      "source_quality": "high",
      "source_category": "disclosure_platform",
      "caveat": "Disclosure platform domain candidate; document-level verification required.",
    }

  if domain in HIGH_QUALITY_DOMAINS or any(_match_domain(domain, item) for item in HIGH_QUALITY_DOMAINS):
    if domain in PUBLIC_FUNDING_DOMAINS:
      category = "public_funding"
    elif domain in NATIONAL_PROJECT_DOMAINS:
      category = "national_project"
    else:
      category = "government"
    return {
      "source_domain": domain,
      "source_quality": "high",
      "source_category": category,
      "caveat": "Public or government source domain; still requires human review for linkage.",
    }

  if domain.endswith(".go.jp") or _match_domain(domain, "go.jp"):
    category = "local_government" if any(h in domain for h in LOCAL_GOVERNMENT_HINTS) else "government"
    return {
      "source_domain": domain,
      "source_quality": "high",
      "source_category": category,
      "caveat": "Government domain; verify page relevance before use.",
    }

  if domain.endswith(".ac.jp") or domain.endswith(".edu"):
    return {
      "source_domain": domain,
      "source_quality": "medium_high",
      "source_category": "university",
      "caveat": "University official domain candidate; confirm publication context.",
    }

  if _looks_like_ir_official(source_url, domain):
    return {
      "source_domain": domain,
      "source_quality": "medium_high",
      "source_category": "ir_official",
      "caveat": "Company IR page candidate; verify document type and fiscal period.",
    }

  if domain.endswith(".co.jp") or domain.endswith(".com") or domain.endswith(".corp"):
    if not any(hint in domain for hint in LOW_QUALITY_HINTS):
      return {
        "source_domain": domain,
        "source_quality": "medium_high",
        "source_category": "ir_official" if "news" in str(source_url).lower() else "company_official",
        "caveat": "Company domain candidate; verify official press release or IR page.",
      }

  if any(hint in domain for hint in LOW_QUALITY_HINTS):
    category = "job_board" if any(j in domain for j in JOB_BOARD_HINTS) else "social"
    if "blog" in domain or "medium.com" in domain or "note.com" in domain:
      category = "blog"
    return {
      "source_domain": domain,
      "source_quality": "low",
      "source_category": category,
      "caveat": "Low-trust domain; use only as weak signal candidate.",
    }

  if any(hint in domain for hint in LOCAL_NEWS_HINTS):
    return {
      "source_domain": domain,
      "source_quality": "medium",
      "source_category": "local_news",
      "caveat": "Local or regional news candidate; verify date and entity linkage.",
    }

  if any(hint in domain for hint in INDUSTRY_MEDIA_HINTS):
    return {
      "source_domain": domain,
      "source_quality": "medium",
      "source_category": "industry_media",
      "caveat": "Industry media candidate; not a final business conclusion.",
    }

  return {
    "source_domain": domain,
    "source_quality": "unknown",
    "source_category": "search_result",
    "caveat": "Unknown domain quality; manual review required.",
  }
